use crate::plan;
use rpt_data::{cell_to_value, Cell, Column, Row, RowSource, ScopeData};
use rpt_formula::Value;
use rpt_model::{FieldValueType, Report};
use serde::Deserialize;
use std::collections::BTreeMap;

#[derive(Deserialize)]
pub struct InputRows {
    pub rows: Vec<Vec<Option<String>>>,
}

#[derive(Clone)]
pub struct MemoryRows {
    columns: Vec<Column>,
    rows: Vec<Row>,
}

impl RowSource for MemoryRows {
    fn columns(&self) -> &[Column] {
        &self.columns
    }
    fn rows(&self) -> Vec<Row> {
        self.rows.clone()
    }
}

pub struct Sources {
    data: BTreeMap<String, MemoryRows>,
    main_key: String,
}

impl Sources {
    pub fn new(report: &Report, mut inputs: BTreeMap<String, InputRows>) -> Result<Self, String> {
        let mut result = Self {
            data: BTreeMap::new(),
            main_key: plan::key(report)?,
        };
        result.insert(
            "main",
            report,
            inputs.remove("main").ok_or("Dataset principal ausente")?,
        )?;
        for sub in &report.subreports {
            let input = inputs
                .remove(&sub.name)
                .ok_or_else(|| format!("Dataset de subrelatorio ausente: {}", sub.name))?;
            result.insert(&sub.name, &sub.report, input)?;
        }
        Ok(result)
    }

    fn insert(&mut self, name: &str, report: &Report, input: InputRows) -> Result<(), String> {
        let query = plan::query(report)?;
        let columns = query.result_columns();
        if input.rows.iter().any(|row| row.len() != columns.len()) {
            return Err(format!("Quantidade de colunas inconsistente: {name}"));
        }
        let mut rows = Vec::new();
        for cells in input.rows {
            let mut row = Row::default();
            for (column, cell) in columns.iter().zip(cells) {
                let cell = cell.map(Cell::Text);
                let value = cell_to_value(column.value_type, cell.as_ref());
                let invalid_boolean = column.value_type == FieldValueType::Boolean
                    && matches!(&cell, Some(Cell::Text(text))
                        if !text.eq_ignore_ascii_case("true") && !text.eq_ignore_ascii_case("false"));
                let non_finite = matches!(&value, Value::Number(number) | Value::Currency(number)
                    if !number.is_finite());
                let typed_text = matches!(
                    column.value_type,
                    FieldValueType::Date | FieldValueType::Time | FieldValueType::DateTime
                );
                if cell.is_some()
                    && (invalid_boolean
                        || non_finite
                        || matches!(value, Value::Null)
                        || (typed_text && matches!(value, Value::Str(_))))
                {
                    return Err(format!("Valor SQL nao convertido: {name}.{}", column.name));
                }
                row.insert(&column.name, value);
            }
            rows.push(row);
        }
        self.data.insert(query.sql, MemoryRows { columns, rows });
        Ok(())
    }

    pub fn main(&self) -> Result<&MemoryRows, String> {
        self.data
            .get(&self.main_key)
            .ok_or_else(|| "Dataset principal indisponivel".into())
    }
}

impl ScopeData for Sources {
    fn rows_for(&self, report: &Report) -> Option<Box<dyn RowSource>> {
        let key = plan::key(report).ok()?;
        self.data
            .get(&key)
            .map(|source| Box::new(source.clone()) as Box<dyn RowSource>)
    }
}
