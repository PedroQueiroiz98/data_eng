interface Props {
  title: string;
  phase: number;
}

export function Placeholder({ title, phase }: Props) {
  return (
    <div>
      <h1 className="text-2xl font-semibold">{title}</h1>
      <p className="mt-2 text-slate-500">
        Tela prevista para a Fase {phase}. Ainda não implementada.
      </p>
    </div>
  );
}
