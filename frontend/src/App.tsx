import { BrowserRouter, Route, Routes } from 'react-router'

import { AppLayout } from './components/AppLayout'
import { DiaryPage } from './pages/DiaryPage'
import { ExplorePage } from './pages/ExplorePage'
import { FeedPage } from './pages/FeedPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { ProfilePage } from './pages/ProfilePage'
import { SearchPage } from './pages/SearchPage'
import { ShelfPage } from './pages/ShelfPage'
import { WorkPage } from './pages/WorkPage'
import { PreferencesProvider } from './providers/PreferencesProvider'
import { SessionProvider } from './providers/SessionProvider'

export function App() {
  return (
    <PreferencesProvider>
      <SessionProvider>
        <BrowserRouter basename="/app-v2">
          <Routes>
            <Route element={<AppLayout />}>
              <Route index element={<SearchPage />} />
              <Route path="explorar" element={<ExplorePage />} />
              <Route path="obra" element={<WorkPage />} />
              <Route path="feed" element={<FeedPage />} />
              <Route path="estante" element={<ShelfPage />} />
              <Route path="diario" element={<DiaryPage />} />
              <Route path="perfil" element={<ProfilePage />} />
              <Route path="perfil/:handle" element={<ProfilePage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </SessionProvider>
    </PreferencesProvider>
  )
}
