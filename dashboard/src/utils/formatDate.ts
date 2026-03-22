/**
 * Shared date formatting utilities for the OpenInsure dashboard.
 * Validates dates before rendering and provides consistent formatting.
 */

/**
 * Safely parse a date value. Returns null if the input is not a valid date.
 */
function safeParseDate(value: string | number | Date | null | undefined): Date | null {
  if (value == null || value === '') return null;
  const d = value instanceof Date ? value : new Date(value);
  return isNaN(d.getTime()) ? null : d;
}

/**
 * Format a date for display. Returns "—" for invalid/missing dates.
 *
 * @param value - Date string, timestamp, or Date object
 * @param style - 'short' for date only, 'long' for date + time
 */
export function formatDate(
  value: string | number | Date | null | undefined,
  style: 'short' | 'long' = 'short',
): string {
  const d = safeParseDate(value);
  if (!d) return '—';

  if (style === 'long') {
    return d.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  return d.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

/**
 * Format a date as a full timestamp string.
 */
export function formatTimestamp(value: string | number | Date | null | undefined): string {
  return formatDate(value, 'long');
}
