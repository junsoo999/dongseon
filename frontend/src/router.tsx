import { createBrowserRouter } from 'react-router'
import { Layout } from './components/Layout'
import { Flights } from './pages/Flights'
import { Home } from './pages/Home'
import { Itinerary } from './pages/Itinerary'
import { More } from './pages/More'
import { Places } from './pages/Places'
import { Stays } from './pages/Stays'
import { Prep } from './pages/Prep'
import { Today } from './pages/Today'
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
      { path: 'itinerary', element: <Itinerary /> },
      { path: 'today', element: <Today /> },
      { path: 'prep', element: <Prep /> },
      { path: 'settings', element: <Settings /> },
      { path: 'more', element: <More /> },
    ],
  },
]

export const router = createBrowserRouter(routes)
