import React from 'react';

/* ── Shared form‐field component ── */

interface BaseProps {
  label: string;
  name: string;
  error?: string;
  required?: boolean;
  className?: string;
}

/* ── Text / Email / Phone ── */
interface TextFieldProps extends BaseProps {
  type: 'text' | 'email' | 'tel';
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

/* ── Number ── */
interface NumberFieldProps extends BaseProps {
  type: 'number';
  value: number | '';
  onChange: (value: number | '') => void;
  placeholder?: string;
  min?: number;
  max?: number;
  step?: number;
}

/* ── Currency ($ prefixed number) ── */
interface CurrencyFieldProps extends BaseProps {
  type: 'currency';
  value: number | '';
  onChange: (value: number | '') => void;
  placeholder?: string;
}

/* ── Select ── */
interface SelectFieldProps extends BaseProps {
  type: 'select';
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  placeholder?: string;
}

/* ── Date ── */
interface DateFieldProps extends BaseProps {
  type: 'date';
  value: string;
  onChange: (value: string) => void;
}

/* ── Checkbox ── */
interface CheckboxFieldProps extends BaseProps {
  type: 'checkbox';
  checked: boolean;
  onChange: (checked: boolean) => void;
}

/* ── Textarea ── */
interface TextareaFieldProps extends BaseProps {
  type: 'textarea';
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  rows?: number;
  minLength?: number;
}

/* ── Slider ── */
interface SliderFieldProps extends BaseProps {
  type: 'slider';
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  step?: number;
}

type FormFieldProps =
  | TextFieldProps
  | NumberFieldProps
  | CurrencyFieldProps
  | SelectFieldProps
  | DateFieldProps
  | CheckboxFieldProps
  | TextareaFieldProps
  | SliderFieldProps;

const inputBase =
  'block w-full rounded-lg border border-slate-200/60 bg-white px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 outline-none transition';
const inputError =
  'border-red-400 focus:border-red-500 focus:ring-red-500';

const FormField: React.FC<FormFieldProps> = (props) => {
  const { label, name, error, required, className = '' } = props;

  /* ── Checkbox layout ── */
  if (props.type === 'checkbox') {
    return (
      <div className={`flex items-center gap-2 ${className}`}>
        <input
          id={name}
          name={name}
          type="checkbox"
          checked={props.checked}
          onChange={(e) => props.onChange(e.target.checked)}
          className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
        />
        <label htmlFor={name} className="text-sm text-slate-700">
          {label}
        </label>
      </div>
    );
  }

  return (
    <div className={className}>
      <label htmlFor={name} className="mb-1 block text-sm font-medium text-slate-700">
        {label}
        {required && <span className="ml-0.5 text-red-500">*</span>}
      </label>

      {/* Text / Email / Phone */}
      {(props.type === 'text' || props.type === 'email' || props.type === 'tel') && (
        <input
          id={name}
          name={name}
          type={props.type}
          value={props.value}
          onChange={(e) => props.onChange(e.target.value)}
          placeholder={props.placeholder}
          required={required}
          className={`${inputBase} ${error ? inputError : ''}`}
        />
      )}

      {/* Number */}
      {props.type === 'number' && (
        <input
          id={name}
          name={name}
          type="number"
          value={props.value}
          onChange={(e) => props.onChange(e.target.value === '' ? '' : Number(e.target.value))}
          placeholder={props.placeholder}
          min={props.min}
          max={props.max}
          step={props.step}
          required={required}
          className={`${inputBase} ${error ? inputError : ''}`}
        />
      )}

      {/* Currency */}
      {props.type === 'currency' && (
        <div className="relative">
          <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-sm text-slate-500">
            $
          </span>
          <input
            id={name}
            name={name}
            type="number"
            value={props.value}
            onChange={(e) => props.onChange(e.target.value === '' ? '' : Number(e.target.value))}
            placeholder={props.placeholder}
            required={required}
            min={0}
            className={`${inputBase} pl-7 ${error ? inputError : ''}`}
          />
        </div>
      )}

      {/* Select */}
      {props.type === 'select' && (
        <select
          id={name}
          name={name}
          value={props.value}
          onChange={(e) => props.onChange(e.target.value)}
          required={required}
          className={`${inputBase} ${error ? inputError : ''}`}
        >
          {props.placeholder && <option value="">{props.placeholder}</option>}
          {props.options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      )}

      {/* Date */}
      {props.type === 'date' && (
        <input
          id={name}
          name={name}
          type="date"
          value={props.value}
          onChange={(e) => props.onChange(e.target.value)}
          required={required}
          className={`${inputBase} ${error ? inputError : ''}`}
        />
      )}

      {/* Textarea */}
      {props.type === 'textarea' && (
        <textarea
          id={name}
          name={name}
          value={props.value}
          onChange={(e) => props.onChange(e.target.value)}
          placeholder={props.placeholder}
          rows={props.rows ?? 4}
          minLength={props.minLength}
          required={required}
          className={`${inputBase} ${error ? inputError : ''}`}
        />
      )}

      {/* Slider */}
      {props.type === 'slider' && (
        <div className="flex items-center gap-3">
          <input
            id={name}
            name={name}
            type="range"
            value={props.value}
            onChange={(e) => props.onChange(Number(e.target.value))}
            min={props.min}
            max={props.max}
            step={props.step ?? 1}
            className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-slate-200 accent-indigo-600"
          />
          <span className="min-w-[2rem] text-center text-sm font-semibold text-slate-700">
            {props.value}
          </span>
        </div>
      )}

      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  );
};

export default FormField;
