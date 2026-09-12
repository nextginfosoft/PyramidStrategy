export type NseHoliday = {
  id: number
  dateStr: string       // 'YYYY-MM-DD'
  dateDisplay: string    // '03-Mar-2026'
  day: string            // 'Tuesday'
  holiday: string        // 'Holi'
}

// NSE trading holiday calendar (2026).
export const NSE_HOLIDAYS: NseHoliday[] = [
  { id: 1, dateStr: '2026-01-15', dateDisplay: '15-Jan-2026', day: 'Thursday', holiday: 'Election - Maharashtra' },
  { id: 2, dateStr: '2026-01-26', dateDisplay: '26-Jan-2026', day: 'Monday', holiday: 'Republic Day' },
  { id: 3, dateStr: '2026-03-03', dateDisplay: '03-Mar-2026', day: 'Tuesday', holiday: 'Holi' },
  { id: 4, dateStr: '2026-03-26', dateDisplay: '26-Mar-2026', day: 'Thursday', holiday: 'Shri Ram Navami' },
  { id: 5, dateStr: '2026-03-31', dateDisplay: '31-Mar-2026', day: 'Tuesday', holiday: 'Shri Mahavir Jayanti' },
  { id: 6, dateStr: '2026-04-03', dateDisplay: '03-Apr-2026', day: 'Friday', holiday: 'Good Friday' },
  { id: 7, dateStr: '2026-04-14', dateDisplay: '14-Apr-2026', day: 'Tuesday', holiday: 'Dr. Baba Saheb Ambedkar Jayanti' },
  { id: 8, dateStr: '2026-05-01', dateDisplay: '01-May-2026', day: 'Friday', holiday: 'Maharashtra Day' },
  { id: 9, dateStr: '2026-05-28', dateDisplay: '28-May-2026', day: 'Thursday', holiday: 'Bakri Id' },
  { id: 10, dateStr: '2026-06-26', dateDisplay: '26-Jun-2026', day: 'Friday', holiday: 'Muharram' },
  { id: 11, dateStr: '2026-09-14', dateDisplay: '14-Sep-2026', day: 'Monday', holiday: 'Ganesh Chaturthi' },
  { id: 12, dateStr: '2026-10-02', dateDisplay: '02-Oct-2026', day: 'Friday', holiday: 'Mahatma Gandhi Jayanti' },
  { id: 13, dateStr: '2026-10-20', dateDisplay: '20-Oct-2026', day: 'Tuesday', holiday: 'Dussehra' },
  { id: 14, dateStr: '2026-11-10', dateDisplay: '10-Nov-2026', day: 'Tuesday', holiday: 'Diwali-Balipratipada' },
  { id: 15, dateStr: '2026-11-24', dateDisplay: '24-Nov-2026', day: 'Tuesday', holiday: 'Prakash Gurpurab Sri Guru Nanak Dev' },
  { id: 16, dateStr: '2026-12-25', dateDisplay: '25-Dec-2026', day: 'Friday', holiday: 'Christmas' },
]

/** Returns the single nearest holiday on or after `fromDate`, or undefined if none remain in the calendar. */
export function getNextHoliday(fromDate: Date = new Date()): NseHoliday | undefined {
  const startOfDay = new Date(fromDate.getFullYear(), fromDate.getMonth(), fromDate.getDate())
  return NSE_HOLIDAYS.find(h => new Date(h.dateStr) >= startOfDay)
}

/** One-line label for the next holiday, noting the pre-poned weekly expiry when it falls on a Tuesday. */
export function formatNextHolidayLine(holiday: NseHoliday): string {
  const suffix = holiday.day === 'Tuesday' ? ' — expiry pre-poned to Mon' : ''
  return `${holiday.dateDisplay.slice(0, 6)} (${holiday.day.slice(0, 3)}) · ${holiday.holiday}${suffix}`
}

/** Whole calendar days between `fromDate` and the holiday's date (0 = today, negative = already past). */
export function daysUntilHoliday(holiday: NseHoliday, fromDate: Date = new Date()): number {
  const startOfDay = new Date(fromDate.getFullYear(), fromDate.getMonth(), fromDate.getDate())
  const target = new Date(holiday.dateStr)
  return Math.round((target.getTime() - startOfDay.getTime()) / 86400000)
}

export type HolidayUrgency = 'calm' | 'soon' | 'today'

/** calm = more than 3 days out, soon = 1-3 days out, today = the holiday itself. */
export function getHolidayUrgency(daysAway: number): HolidayUrgency {
  if (daysAway <= 0) return 'today'
  if (daysAway <= 3) return 'soon'
  return 'calm'
}
