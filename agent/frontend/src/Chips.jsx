export default function Chips({ values }) {
  return (
    <span className="chips">
      {values.map((v) => (
        <code key={v}>{v}</code>
      ))}
    </span>
  );
}
