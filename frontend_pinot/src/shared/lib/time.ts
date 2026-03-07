export function shortTs(value?: string) {
  if (!value) {
    return '-'
  }
  return value.replace('T', ' ').replace('+00:00', ' UTC').slice(0, 23)
}