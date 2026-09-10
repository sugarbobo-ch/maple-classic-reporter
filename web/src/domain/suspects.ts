/** Names are kept verbatim; only explicit list separators are removed. */
export function splitSuspects(value: string): string[] {
  return [...new Set(value.split(/[\s,，]+/u).filter(Boolean))];
}

export function appendSuspects(names: string[], value: string): string[] {
  return [...new Set([...names, ...splitSuspects(value)])];
}
