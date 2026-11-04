import { createBrowserRouter } from 'react-router'
import { Layout } from './components/Layout'
import { Home } from './pages/Home'
import { More } from './pages/More'
import { Placeholder } from './pages/Placeholder'
import { Places } from './pages/Places'
import { Settings } from './pages/Settings'

export const routes = [
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <Home /> },
      { path: 'places', element: <Places /> },
      { path: 'stays', element: <Placeholder title="숙소" milestone="M2" /> },
      { path: 'flights', element: <Placeholder title="항공" milestone="M2" /> },
      { path: 'itinerary', element: <Placeholder title="일정" milestone="M3" /> },
      { path: 'today', element: <Placeholder title="오늘" milestone="M5" /> },
      { path: 'prep', element: <Placeholder title="준비" milestone="M5" /> },
      { path: 'settings', element: <Settings /> },
      { path: 'more', element: <More /> },
    ],
  },
]

export const router = createBrowserRouter(routes)
