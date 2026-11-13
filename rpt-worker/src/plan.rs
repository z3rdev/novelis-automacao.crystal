use rpt_model::Report;
use rpt_query::{build_query_for_report, Dialect, SqlQuery};
use serde_json::{json, Value};

pub fn query(report: &Report) -> Result<SqlQuery, String> {
    let expressions: Vec<_> = report
        .data_definition
        .sql_expression_fields()
        .map(|(field, expression)| (field.name.clone(), expression.text.clone()))
        .collect();
    build_query_for_report(report, &expressions, None, &[], Dialect::Sqlite)
        .map_err(|error| error.to_string())
}

pub fn key(report: &Report) -> Result<String, String> {
    Ok(query(report)?.sql)
}

pub fn scopes(report: &Report) -> Result<Vec<Value>, String> {
    let mut result = vec![scope("main", report)?];
    for sub in &report.subreports {
        result.push(scope(&sub.name, &sub.report)?);
    }
    Ok(result)
}

fn scope(name: &str, report: &Report) -> Result<Value, String> {
    let query = query(report)?;
    let columns: Vec<_> = query
        .columns
        .iter()
        .map(|column| {
            json!({
                "key": column.key(), "alias": column.alias, "field": column.field,
                "value_type": column.value_type, "expression": column.expr,
            })
        })
        .collect();
    Ok(
        json!({"name": name, "key": query.sql, "sql": query.sql, "columns": columns,
              "tables": report.database.tables.iter().map(|table| &table.alias).collect::<Vec<_>>()}),
    )
}
