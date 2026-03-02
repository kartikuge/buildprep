import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface UserState {
  userId: string | null
  displayName: string | null
  weekStart: string | null
  selectedDay: string | null
  prelimsDate: string | null
  firstWeekStart: string | null
  setUser: (
    userId: string,
    displayName: string,
    weekStart: string | null,
    prelimsDate?: string | null,
    firstWeekStart?: string | null,
  ) => void
  setWeekStart: (weekStart: string) => void
  setSelectedDay: (day: string | null) => void
  logout: () => void
}

export const useUserStore = create<UserState>()(
  persist(
    (set) => ({
      userId: null,
      displayName: null,
      weekStart: null,
      selectedDay: null,
      prelimsDate: null,
      firstWeekStart: null,
      setUser: (userId, displayName, weekStart, prelimsDate, firstWeekStart) =>
        set({
          userId,
          displayName,
          weekStart,
          prelimsDate: prelimsDate ?? null,
          firstWeekStart: firstWeekStart ?? weekStart,
        }),
      setWeekStart: (weekStart) => set({ weekStart, selectedDay: null }),
      setSelectedDay: (day) => set({ selectedDay: day }),
      logout: () =>
        set({
          userId: null,
          displayName: null,
          weekStart: null,
          selectedDay: null,
          prelimsDate: null,
          firstWeekStart: null,
        }),
    }),
    { name: 'preptrack-user' },
  ),
)
