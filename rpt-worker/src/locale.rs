use rpt_format_value::{DateOrder, NegativeStyle};
use rpt_render::Locale;

pub fn portuguese_brazil() -> Locale {
    let mut locale = Locale::default();
    locale.tag = "pt-BR";
    locale.decimal_sep = ',';
    locale.thousands_sep = '.';
    locale.date_sep = '/';
    locale.date_order = DateOrder::DayMonthYear;
    locale.short_date_leading_zero = true;
    locale.twelve_hour = false;
    locale.currency_symbol = "R$";
    locale.currency_negative = NegativeStyle::LeadingMinus;
    locale.months = &[
        "janeiro",
        "fevereiro",
        "março",
        "abril",
        "maio",
        "junho",
        "julho",
        "agosto",
        "setembro",
        "outubro",
        "novembro",
        "dezembro",
    ];
    locale.months_abbrev = &[
        "jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez",
    ];
    locale.days = &[
        "domingo",
        "segunda-feira",
        "terça-feira",
        "quarta-feira",
        "quinta-feira",
        "sexta-feira",
        "sábado",
    ];
    locale.days_abbrev = &["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];
    locale
}
