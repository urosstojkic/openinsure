/**
 * Shared LOB (Line of Business) display name mapper.
 * Handles all known API slugs and gracefully humanizes unknown ones.
 */

const LOB_DISPLAY_NAMES: Record<string, string> = {
  cyber: 'Cyber Liability',
  professional_liability: 'Professional Liability',
  dnol: 'Directors & Officers',
  epli: 'Employment Practices',
  general_liability: 'General Liability',
  tech_eo: 'Technology E&O',
  commercial_property: 'Commercial Property',
  mpl: 'Medical Professional Liability',
  commercial_auto: 'Commercial Auto',
  workers_comp: 'Workers\' Compensation',
  bop: 'Business Owner\'s Policy',
  umbrella: 'Umbrella / Excess',
  product_liability: 'Product Liability',
  fiduciary: 'Fiduciary Liability',
  crime: 'Crime',
  marine: 'Marine',
  aviation: 'Aviation',
  environmental: 'Environmental',
};

const LOB_SHORT_NAMES: Record<string, string> = {
  cyber: 'Cyber',
  professional_liability: 'Prof Liability',
  dnol: 'D&O',
  epli: 'EPLI',
  general_liability: 'General Liability',
  tech_eo: 'Tech E&O',
  commercial_property: 'Commercial Property',
  mpl: 'Medical Prof',
  commercial_auto: 'Commercial Auto',
  workers_comp: 'Workers\' Comp',
  bop: 'BOP',
  umbrella: 'Umbrella',
  product_liability: 'Product Liability',
  fiduciary: 'Fiduciary',
  crime: 'Crime',
  marine: 'Marine',
  aviation: 'Aviation',
  environmental: 'Environmental',
};

function humanize(slug: string): string {
  return slug
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Full display name for a LOB slug (e.g. "tech_eo" -> "Technology E&O") */
export function lobDisplayName(lob: string): string {
  return LOB_DISPLAY_NAMES[lob] ?? humanize(lob);
}

/** Short display name for table columns (e.g. "professional_liability" -> "Prof Liability") */
export function lobShortName(lob: string): string {
  return LOB_SHORT_NAMES[lob] ?? humanize(lob);
}
