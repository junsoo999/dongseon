import { createBrowserRouter } from 'react-router'
import { Layout } from './components/Layout'
import { Flights } from './pages/Flights'
import { Home } from './pages/Home'
import { More } from './pages/More'
import { Placeholder } from './pages/Placeholder'
import { Places } from './pages/Places'
import { Stays } from './pages/Stays'
import { Settings } from './pages/Settings'

export const routes = [
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <Home /> },
      { path: 'places', element: <Places /> },
      { path: 'stays', element: <Stays /> },
      { path: 'flights', element: <Flights /> },
      { path: 'itinerary', element: <Placeholder title="일정" milestone="M3" /> },
      { path: 'today', element: <Placeholder title="오늘" milestone="M5" /> },
      { path: 'prep', element: <Placeholder title="준비" milestone="M5" /> },
      { path: 'settings', element: <Settings /> },
      { path: 'more', element: <More /> },
    ],
  },
]

export const router = createBrowserRouter(routes)
