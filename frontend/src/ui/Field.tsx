import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";

const base =
  "w-full rounded-md border border-surface-border bg-surface px-3 py-2 text-sm text-fg " +
  "placeholder:text-fg-faint focus:outline-none focus:ring-2 focus:ring-primary/40 " +
  "focus:border-primary disabled:opacity-60";

function Wrap({
  label,
  hint,
  error,
  children,
}: {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  children: ReactNode;
}) {
  return (
    <label className="block">
      {label && (
        <span className="mb-1 block text-xs font-medium text-fg-muted">{label}</span>
      )}
      {children}
      {error ? (
        <span className="mt-1 block text-xs text-danger">{error}</span>
      ) : hint ? (
        <span className="mt-1 block text-xs text-fg-faint">{hint}</span>
      ) : null}
    </label>
  );
}

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  mono?: boolean;
}

export function TextField({ label, hint, error, mono, className = "", ...rest }: TextFieldProps) {
  return (
    <Wrap label={label} hint={hint} error={error}>
      <input className={`${base} ${mono ? "font-mono" : ""} ${className}`} {...rest} />
    </Wrap>
  );
}

interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
}

export function SelectField({ label, hint, error, className = "", children, ...rest }: SelectFieldProps) {
  return (
    <Wrap label={label} hint={hint} error={error}>
      <select className={`${base} ${className}`} {...rest}>
        {children}
      </select>
    </Wrap>
  );
}

interface TextAreaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
}

export function TextArea({ label, hint, error, className = "", ...rest }: TextAreaProps) {
  return (
    <Wrap label={label} hint={hint} error={error}>
      <textarea className={`${base} font-mono ${className}`} {...rest} />
    </Wrap>
  );
}

export function Switch({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label?: ReactNode;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className="inline-flex items-center gap-2 text-sm text-fg"
    >
      <span
        className={`relative h-5 w-9 rounded-full transition ${
          checked ? "bg-primary" : "bg-fg/25"
        }`}
      >
        <span
          className={`absolute top-0.5 h-4 w-4 rounded-full bg-surface shadow transition ${
            checked ? "left-4" : "left-0.5"
          }`}
        />
      </span>
      {label}
    </button>
  );
}
