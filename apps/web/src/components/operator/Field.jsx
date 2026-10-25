/** Campo con etiqueta del operador. `props` admite required, pattern, min, max, readOnly… */
export function Field({ label, name, defaultValue = '', type = 'text', ...props }) {
  return <label className="op-field"><span>{label}</span><input name={name} type={type} defaultValue={defaultValue} {...props} /></label>;
}
