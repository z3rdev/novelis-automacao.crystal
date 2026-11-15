#[derive(Clone, Copy, Debug, PartialEq, serde::Serialize)]
#[serde(rename_all = "snake_case")]
pub enum NetworkKind {
    Wifi,
    Ethernet,
    Vpn,
    Cellular,
    Offline,
    Unknown,
}

#[derive(Debug, serde::Serialize)]
pub struct NetworkStatus {
    kind: NetworkKind,
    transport: Option<NetworkKind>,
}

#[tauri::command]
pub async fn network_status() -> Result<NetworkStatus, String> {
    tauri::async_runtime::spawn_blocking(read_network)
        .await
        .map_err(|_| "Não foi possível consultar a rede do Windows.".to_string())?
}

#[cfg(not(windows))]
fn read_network() -> Result<NetworkStatus, String> {
    Ok(NetworkStatus {
        kind: NetworkKind::Unknown,
        transport: None,
    })
}

#[cfg(windows)]
mod windows_network {
    use super::{NetworkKind, NetworkStatus};
    use std::ptr::null;
    use windows_sys::Win32::{
        Foundation::{ERROR_BUFFER_OVERFLOW, ERROR_NO_DATA, NO_ERROR},
        NetworkManagement::{IpHelper::*, Ndis::IfOperStatusUp},
        Networking::WinSock::*,
    };

    struct Adapter {
        index: u32,
        ipv6_index: u32,
        kind: NetworkKind,
        has_gateway: bool,
    }

    fn adapter_kind(interface_type: u32, description: &str) -> NetworkKind {
        let description = description.to_ascii_lowercase();
        let vpn = [
            "wireguard",
            "wintun",
            "openvpn",
            "tap-windows",
            "vpn",
            "fortinet",
            "forticlient",
            "anyconnect",
            "globalprotect",
            "tailscale",
            "zerotier",
        ]
        .iter()
        .any(|name| description.contains(name));
        if vpn || interface_type == IF_TYPE_PPP {
            return NetworkKind::Vpn;
        }
        match interface_type {
            IF_TYPE_IEEE80211 => NetworkKind::Wifi,
            IF_TYPE_ETHERNET_CSMACD => NetworkKind::Ethernet,
            IF_TYPE_WWANPP | IF_TYPE_WWANPP2 => NetworkKind::Cellular,
            _ => NetworkKind::Unknown,
        }
    }

    // Windows supplies these null-terminated strings inside the live adapter buffer.
    unsafe fn description(pointer: *const u16) -> String {
        if pointer.is_null() {
            return String::new();
        }
        let mut length = 0;
        while *pointer.add(length) != 0 {
            length += 1;
        }
        String::from_utf16_lossy(std::slice::from_raw_parts(pointer, length))
    }

    fn best_interface() -> Option<u32> {
        // Route lookups only. These calls send no traffic to the destination addresses.
        let ipv4 = SOCKADDR_IN {
            sin_family: AF_INET,
            sin_addr: IN_ADDR {
                S_un: IN_ADDR_0 {
                    S_addr: u32::from_ne_bytes([1, 1, 1, 1]),
                },
            },
            ..Default::default()
        };
        let mut index = 0;
        if unsafe { GetBestInterfaceEx((&ipv4 as *const SOCKADDR_IN).cast(), &mut index) }
            == NO_ERROR
        {
            return Some(index);
        }
        let ipv6 = SOCKADDR_IN6 {
            sin6_family: AF_INET6,
            sin6_addr: IN6_ADDR {
                u: IN6_ADDR_0 {
                    Byte: [
                        0x26, 0x06, 0x47, 0, 0x47, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0x11, 0x11,
                    ],
                },
            },
            ..Default::default()
        };
        (unsafe { GetBestInterfaceEx((&ipv6 as *const SOCKADDR_IN6).cast(), &mut index) }
            == NO_ERROR)
            .then_some(index)
    }

    fn select(adapters: &[Adapter], best: Option<u32>) -> NetworkStatus {
        let routed = adapters.iter().find(|adapter| {
            best.is_some_and(|index| adapter.index == index || adapter.ipv6_index == index)
        });
        let transport = routed
            .filter(|adapter| adapter.kind != NetworkKind::Vpn)
            .or_else(|| {
                adapters.iter().find(|adapter| {
                    adapter.has_gateway
                        && matches!(
                            adapter.kind,
                            NetworkKind::Wifi | NetworkKind::Ethernet | NetworkKind::Cellular
                        )
                })
            })
            .map(|adapter| adapter.kind);
        let kind = if adapters
            .iter()
            .any(|adapter| adapter.kind == NetworkKind::Vpn)
        {
            NetworkKind::Vpn
        } else if let Some(adapter) = routed {
            adapter.kind
        } else {
            transport.unwrap_or(NetworkKind::Offline)
        };
        NetworkStatus {
            kind,
            transport: (kind == NetworkKind::Vpn).then_some(transport).flatten(),
        }
    }

    pub(super) fn read() -> Result<NetworkStatus, String> {
        let mut bytes = 15_000u32;
        for _ in 0..3 {
            // u64 gives the alignment required by IP_ADAPTER_ADDRESSES_LH.
            let mut buffer = vec![0u64; bytes.div_ceil(8) as usize];
            let result = unsafe {
                GetAdaptersAddresses(
                    AF_UNSPEC as u32,
                    GAA_FLAG_SKIP_ANYCAST
                        | GAA_FLAG_SKIP_MULTICAST
                        | GAA_FLAG_SKIP_DNS_SERVER
                        | GAA_FLAG_INCLUDE_GATEWAYS,
                    null(),
                    buffer.as_mut_ptr().cast(),
                    &mut bytes,
                )
            };
            if result == ERROR_BUFFER_OVERFLOW {
                continue;
            }
            if result == ERROR_NO_DATA {
                return Ok(select(&[], None));
            }
            if result != NO_ERROR {
                break;
            }
            let mut pointer = buffer.as_ptr().cast::<IP_ADAPTER_ADDRESSES_LH>();
            let mut adapters = Vec::new();
            // All linked records and strings remain owned by buffer throughout this traversal.
            unsafe {
                while !pointer.is_null() {
                    let adapter = &*pointer;
                    if adapter.OperStatus == IfOperStatusUp
                        && adapter.IfType != IF_TYPE_SOFTWARE_LOOPBACK
                        && !adapter.FirstUnicastAddress.is_null()
                    {
                        adapters.push(Adapter {
                            index: adapter.Anonymous1.Anonymous.IfIndex,
                            ipv6_index: adapter.Ipv6IfIndex,
                            kind: adapter_kind(adapter.IfType, &description(adapter.Description)),
                            has_gateway: !adapter.FirstGatewayAddress.is_null(),
                        });
                    }
                    pointer = adapter.Next;
                }
            }
            return Ok(select(&adapters, best_interface()));
        }
        Err("Não foi possível consultar os adaptadores de rede.".into())
    }

    #[cfg(test)]
    mod tests {
        use super::*;
        #[test]
        fn reads_the_current_windows_network() {
            let value = read().expect("Windows network API");
            println!("WINDOWS_NETWORK={:?}", value.kind);
        }
        #[test]
        fn uses_windows_interface_types_and_vpn_drivers() {
            assert_eq!(
                adapter_kind(IF_TYPE_IEEE80211, "Wireless adapter"),
                NetworkKind::Wifi
            );
            assert_eq!(
                adapter_kind(IF_TYPE_ETHERNET_CSMACD, "Intel Ethernet"),
                NetworkKind::Ethernet
            );
            assert_eq!(
                adapter_kind(IF_TYPE_ETHERNET_CSMACD, "TAP-Windows Adapter V9"),
                NetworkKind::Vpn
            );
            assert_eq!(adapter_kind(IF_TYPE_PPP, "WAN Miniport"), NetworkKind::Vpn);
            assert_eq!(adapter_kind(IF_TYPE_TUNNEL, "Teredo"), NetworkKind::Unknown);
        }
        #[test]
        fn selects_the_routed_adapter_and_marks_split_tunnel_vpn() {
            let mut adapters = vec![
                Adapter {
                    index: 1,
                    ipv6_index: 1,
                    kind: NetworkKind::Ethernet,
                    has_gateway: false,
                },
                Adapter {
                    index: 2,
                    ipv6_index: 2,
                    kind: NetworkKind::Wifi,
                    has_gateway: true,
                },
            ];
            assert_eq!(select(&adapters, Some(2)).kind, NetworkKind::Wifi);
            adapters.push(Adapter {
                index: 3,
                ipv6_index: 3,
                kind: NetworkKind::Vpn,
                has_gateway: false,
            });
            let result = select(&adapters, Some(2));
            assert_eq!(result.kind, NetworkKind::Vpn);
            assert_eq!(result.transport, Some(NetworkKind::Wifi));
            assert_eq!(select(&[], None).kind, NetworkKind::Offline);
        }
    }
}

#[cfg(windows)]
fn read_network() -> Result<NetworkStatus, String> {
    windows_network::read()
}
