import React from 'react';

interface SparklineProps {
  /** Series (null entries are skipped — not recorded, never interpolated). */
  data: (number | null | undefined)[] | null | undefined;
  color: string;
  width?: number;
  height?: number;
  className?: string;
  /** Number of trailing recorded samples to draw (default 80). */
  window?: number;
}

/**
 * Tiny SVG trend line over the trailing recorded samples of a series.
 * Renders nothing when fewer than 2 recorded samples exist — the honest
 * empty state is handled by the surrounding card ("—" / not recorded).
 */
export const Sparkline: React.FC<SparklineProps> = ({
  data,
  color,
  width = 72,
  height = 16,
  className = '',
  window = 80,
}) => {
  const clean = (data ?? [])
    .filter((v): v is number => v != null && !Number.isNaN(v))
    .slice(-window);

  if (clean.length < 2) return null;

  const min = Math.min(...clean);
  const max = Math.max(...clean);
  const span = max - min || Math.abs(max) || 1;
  const pad = 2;

  const points = clean
    .map((v, i) => {
      const x = pad + (i / (clean.length - 1)) * (width - pad * 2);
      const y = height - pad - ((v - min) / span) * (height - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={`overflow-visible ${className}`}
      aria-hidden="true"
    >
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.3"
        strokeLinejoin="round"
        strokeLinecap="round"
        opacity="0.9"
      />
    </svg>
  );
};
