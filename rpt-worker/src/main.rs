mod data;
mod locale;
mod plan;

use rpt_data::Parameters;
use rpt_formula::Value;
use rpt_model::Report;
use rpt_render::{render_with, FontSource, RenderOptions, RenderSource};
use rpt_render_pdf::{try_render_document, PdfOptions};
use serde::Deserialize;
use serde_json::{json, Value as Json};
use std::collections::BTreeMap;
use std::io::{self, Read};
use std::path::PathBuf;

const REVISION: &str = "3f5beb51dd34d36c4a4326280d25f473b44889d1";

#[derive(Deserialize)]
struct Request {
    action: String,
    report_path: Option<PathBuf>,
    model: Option<Report>,
    output_path: Option<PathBuf>,
    #[serde(default)]
    parameters: BTreeMap<String, Json>,
    #[serde(default)]
    datasets: BTreeMap<String, data::InputRows>,
    #[serde(default)]
    system_fonts: bool,
}

fn parameters(values: &BTreeMap<String, Json>) -> Result<Parameters, String> {
    values
        .iter()
        .map(|(name, value)| {
            let value = match value {
                Json::String(text) => Value::Str(text.clone()),
                Json::Number(number) => {
                    Value::Number(number.as_f64().ok_or("Parametro numerico invalido")?)
                }
                Json::Bool(value) => Value::Bool(*value),
                Json::Null => Value::Null,
                _ => return Err("Tipo de parametro nao suportado".into()),
            };
            Ok((rpt_data::normalize_param_name(name), value))
        })
        .collect()
}

fn run(request: Request) -> Result<Json, String> {
    let report = match request.model {
        Some(model) => model,
        None => rpt_reader::Rpt::open(request.report_path.ok_or("Informe report_path")?)
            .map_err(|error| error.to_string())?
            .report()
            .clone(),
    };
    match request.action.as_str() {
        "inspect" => Ok(json!({"ok": true, "revision": REVISION, "model": report})),
        "plan" => Ok(json!({"ok": true, "revision": REVISION, "scopes": plan::scopes(&report)?})),
        "render" => {
            let sources = data::Sources::new(&report, request.datasets)?;
            let main = sources.main()?;
            let fonts = if request.system_fonts {
                FontSource::System
            } else {
                FontSource::Bundled
            };
            let pages = render_with(
                &report,
                RenderOptions {
                    datasource: RenderSource::Rows(main),
                    params: parameters(&request.parameters)?,
                    locale: locale::portuguese_brazil(),
                    scope: Some(&sources),
                    fonts,
                    ..RenderOptions::default()
                },
            );
            let pdf = try_render_document(
                &pages,
                &PdfOptions {
                    fonts,
                    ..PdfOptions::default()
                },
            )
            .map_err(|error| error.to_string())?;
            std::fs::write(request.output_path.ok_or("Informe output_path")?, &pdf)
                .map_err(|error| error.to_string())?;
            Ok(
                json!({"ok": true, "revision": REVISION, "pages": pages.pages.len(),
                      "diagnostics": pages.diagnostics, "type_conversion": "reject_invalid_present_values",
                      "pdf_bytes": pdf.len()}),
            )
        }
        _ => Err("Acao deve ser inspect, plan ou render".into()),
    }
}

fn main() {
    let result = (|| {
        let mut input = String::new();
        io::stdin()
            .read_to_string(&mut input)
            .map_err(|error| error.to_string())?;
        let request: Request = serde_json::from_str(&input).map_err(|error| error.to_string())?;
        run(request)
    })();
    match result {
        Ok(value) => println!("{value}"),
        Err(message) => {
            println!(
                "{}",
                json!({"ok": false, "error": message, "revision": REVISION})
            );
            std::process::exit(1);
        }
    }
}
