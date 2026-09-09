'use client'

import * as React from 'react'
import {
  ThemeProvider as NextThemesProvider,
  useTheme,
  type ThemeProviderProps,
} from 'next-themes'

export const SCHEME_STORAGE_KEY = 'lexgentium.scheme'
export const SCHEMES = ['ink', 'parchment', 'seal'] as const
export type ColorScheme = (typeof SCHEMES)[number]

type Listener = () => void

const listeners = new Set<Listener>()

function isScheme(value: unknown): value is ColorScheme {
  return value === 'ink' || value === 'parchment' || value === 'seal'
}

function readStoredScheme(): ColorScheme {
  if (typeof window === 'undefined') return 'ink'
  try {
    const raw = window.localStorage.getItem(SCHEME_STORAGE_KEY)
    return isScheme(raw) ? raw : 'ink'
  } catch {
    return 'ink'
  }
}

function applySchemeAttr(scheme: ColorScheme) {
  document.documentElement.setAttribute('data-scheme', scheme)
}

function emitScheme() {
  listeners.forEach((listener) => listener())
}

function subscribeScheme(listener: Listener) {
  listeners.add(listener)
  const onStorage = (event: StorageEvent) => {
    if (event.key === SCHEME_STORAGE_KEY || event.key === null) listener()
  }
  window.addEventListener('storage', onStorage)
  return () => {
    listeners.delete(listener)
    window.removeEventListener('storage', onStorage)
  }
}

function writeScheme(scheme: ColorScheme) {
  try {
    window.localStorage.setItem(SCHEME_STORAGE_KEY, scheme)
  } catch {
    // private mode / quota
  }
  applySchemeAttr(scheme)
  emitScheme()
}

const SCHEME_INIT_SCRIPT = `(function(){try{var s=localStorage.getItem(${JSON.stringify(SCHEME_STORAGE_KEY)});if(s==='ink'||s==='parchment'||s==='seal'){document.documentElement.setAttribute('data-scheme',s)}else{document.documentElement.setAttribute('data-scheme','ink')}}catch(e){document.documentElement.setAttribute('data-scheme','ink')}})();`

export function useColorScheme() {
  const { setTheme } = useTheme()
  const scheme = React.useSyncExternalStore(subscribeScheme, readStoredScheme, () => 'ink' as ColorScheme)

  const setScheme = React.useCallback(
    (next: ColorScheme) => {
      writeScheme(next)
      if (next === 'parchment') {
        setTheme('light')
      }
    },
    [setTheme],
  )

  return { scheme, setScheme }
}

function SchemeApplier() {
  const scheme = React.useSyncExternalStore(subscribeScheme, readStoredScheme, () => 'ink' as ColorScheme)

  React.useLayoutEffect(() => {
    applySchemeAttr(scheme)
  }, [scheme])

  return null
}

export function ThemeProvider({ children, ...props }: ThemeProviderProps) {
  return (
    <NextThemesProvider {...props}>
      <script dangerouslySetInnerHTML={{ __html: SCHEME_INIT_SCRIPT }} />
      <SchemeApplier />
      {children}
    </NextThemesProvider>
  )
}
