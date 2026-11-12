import { createContext, useContext, useState, useEffect } from 'react'

const UIContext = createContext(null)

const getMobile = () => typeof window !== 'undefined' && window.innerWidth < 768
const getTablet = () => typeof window !== 'undefined' && window.innerWidth >= 768 && window.innerWidth < 1024

export function UIProvider({ children }) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => getMobile() || getTablet())
  const [notifCount, setNotifCount] = useState(0)
  const [isMobile, setIsMobile] = useState(getMobile)
  const [isTablet, setIsTablet] = useState(getTablet)
  const [wsStatus, setWsStatus] = useState('connecting')

  useEffect(() => {
    const handler = () => {
      const mobile = getMobile()
      const tablet = getTablet()
      setIsMobile(mobile)
      setIsTablet(tablet)
      if (mobile || tablet) setSidebarCollapsed(true)
    }
    window.addEventListener('resize', handler, { passive: true })
    handler()
    return () => window.removeEventListener('resize', handler)
  }, [])

  const toggleSidebar = () => setSidebarCollapsed((prev) => !prev)

  return (
    <UIContext.Provider value={{
      sidebarCollapsed, setSidebarCollapsed, toggleSidebar,
      notifCount, setNotifCount,
      isMobile,
      isTablet,
      wsStatus, setWsStatus,
    }}>
      {children}
    </UIContext.Provider>
  )
}

export function useUI() {
  const ctx = useContext(UIContext)
  if (!ctx) throw new Error('useUI must be used within UIProvider')
  return ctx
}
