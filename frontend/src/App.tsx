import { useUserStore } from './store/userStore'
import { OnboardingWizard } from './components/onboarding/OnboardingWizard'
import { CalendarView } from './components/calendar/CalendarView'

export default function App() {
  const userId = useUserStore((s) => s.userId)

  if (!userId) {
    return <OnboardingWizard />
  }

  return <CalendarView />
}
