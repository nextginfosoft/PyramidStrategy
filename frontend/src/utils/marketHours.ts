import { NSE_HOLIDAYS } from './nseHolidays'

const IST_TIME_ZONE = 'Asia/Kolkata'
const TRADING_WEEKDAYS = new Set(['Mon', 'Tue', 'Wed', 'Thu', 'Fri'])

// NSE cash/derivatives session: 9:15 AM - 3:30 PM IST
const MARKET_OPEN_MINUTES = 9 * 60 + 15
const MARKET_CLOSE_MINUTES = 15 * 60 + 30

function getIstParts(date: Date) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: IST_TIME_ZONE,
    weekday: 'short',
    hour: 'numeric',
    minute: 'numeric',
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date)

  const get = (type: string) => parts.find(p => p.type === type)?.value ?? ''
  return {
    weekday: get('weekday'),
    hour: parseInt(get('hour'), 10),
    minute: parseInt(get('minute'), 10),
    dateStr: `${get('year')}-${get('month')}-${get('day')}`,
  }
}

/**
 * Whether NSE cash/derivatives trading is currently in session — Mon-Fri,
 * 9:15 AM-3:30 PM IST, excluding NSE holidays — computed in IST regardless
 * of the viewer's own local timezone.
 */
export function isMarketOpenNow(date: Date = new Date()): boolean {
  const { weekday, hour, minute, dateStr } = getIstParts(date)

  if (!TRADING_WEEKDAYS.has(weekday)) return false
  if (NSE_HOLIDAYS.some(h => h.dateStr === dateStr)) return false

  const minutesSinceMidnight = hour * 60 + minute
  return minutesSinceMidnight >= MARKET_OPEN_MINUTES && minutesSinceMidnight < MARKET_CLOSE_MINUTES
}
