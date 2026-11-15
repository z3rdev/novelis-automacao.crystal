export interface DateRange { dataInicio: string; dataFim: string }
export interface MessageConfiguration {
  title: string;
  signature: string;
  message: string;
  complement_message: string;
  allow_missing_receipt: boolean;
}
export const localDate = (value: Date) => `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
export function dateLimits() {
  const today = new Date();
  const earliest = new Date(today);
  earliest.setDate(today.getDate() - 30);
  return { min: localDate(earliest), max: localDate(today) };
}
export function periodError(range: DateRange) {
  const limits = dateLimits();
  if (!range.dataInicio || !range.dataFim) return "Informe as duas datas.";
  if (range.dataInicio > range.dataFim) return "A data inicial deve ser anterior ou igual à final.";
  if (range.dataInicio < limits.min || range.dataFim > limits.max) return "Escolha datas entre hoje e 30 dias atrás.";
  return null;
}
