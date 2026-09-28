import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import i18n from '../i18n'
import { ThemeProvider } from '../contexts/ThemeContext'
import ClothesDetail from '../pages/ClothesDetail'
import Outfit from '../pages/Outfit'

const garment = {
  id: 1,
  item: 'Jacket',
  category: 'top',
  description: 'A black jacket',
  image_url: '/uploads/jacket.png',
  color_semantics: 'black',
  style_semantics: [],
  season_semantics: [],
  usage_semantics: [],
}

const wardrobeResponse = {
  tops: [{ id: 11, item: 'Jacket', image_url: '/uploads/jacket.png', season_semantics: [] }],
  bottoms: [{ id: 22, item: 'Pants', image_url: '/uploads/pants.png', season_semantics: [] }],
  shoes: [{ id: 33, item: 'Sneakers', image_url: '/uploads/shoes.png', season_semantics: [] }],
  accessories: [],
}

const renderClothesDetail = () => render(
  <ThemeProvider>
    <MemoryRouter initialEntries={['/clothes/1']}>
      <Routes>
        <Route path="/clothes/:id" element={<ClothesDetail />} />
      </Routes>
    </MemoryRouter>
  </ThemeProvider>,
)

const renderOutfit = () => render(
  <ThemeProvider>
    <MemoryRouter>
      <Outfit />
    </MemoryRouter>
  </ThemeProvider>,
)

function stubFetch({ hasPersonImage }) {
  const calls = []
  const fetchMock = vi.fn(async (url, options = {}) => {
    const requestUrl = String(url)
    calls.push({ url: requestUrl, options })

    if (requestUrl.endsWith('/config')) {
      return {
        ok: true,
        json: async () => ({
          has_person_image: hasPersonImage,
          person_image_url: hasPersonImage ? '/uploads/person/person.png' : '',
        }),
      }
    }

    if (requestUrl.endsWith('/wardrobe')) {
      return { ok: true, json: async () => wardrobeResponse }
    }

    if (requestUrl.endsWith('/clothes/1')) {
      return { ok: true, json: async () => garment }
    }

    if (requestUrl.endsWith('/tryon') && options.method === 'POST') {
      return { ok: true, json: async () => ({ success: true, result_image_url: '/uploads/tryon/result.png' }) }
    }

    return { ok: false, json: async () => ({}) }
  })

  vi.stubGlobal('fetch', fetchMock)
  return calls
}

const tryOnPosts = (calls) => calls.filter(
  (call) => call.url.endsWith('/tryon') && call.options?.method === 'POST',
)

describe('AI try-on flow', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    i18n.changeLanguage('en')
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('generates a try-on for a single garment from the detail page', async () => {
    const calls = stubFetch({ hasPersonImage: true })
    renderClothesDetail()

    const button = await screen.findByRole('button', { name: 'Generate try-on' })
    await waitFor(() => expect(button.disabled).toBe(false))
    fireEvent.click(button)

    const posts = tryOnPosts(calls)
    await waitFor(() => expect(posts).toHaveLength(1))
    expect(JSON.parse(posts[0].options.body)).toEqual({ garment_ids: [1] })

    expect(await screen.findByAltText('Try-on result')).toBeTruthy()
  })

  it('prompts for a photo from the detail page when none is uploaded', async () => {
    const calls = stubFetch({ hasPersonImage: false })
    renderClothesDetail()

    const button = await screen.findByRole('button', { name: 'Generate try-on' })
    await waitFor(() => expect(button.disabled).toBe(false))
    fireEvent.click(button)

    expect(await screen.findByText('No photo yet')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Open Settings' })).toBeTruthy()
    expect(tryOnPosts(calls)).toHaveLength(0)
  })

  it('generates a try-on for the whole outfit from the outfit page', async () => {
    const calls = stubFetch({ hasPersonImage: true })
    renderOutfit()

    const button = await screen.findByRole('button', { name: 'Generate try-on' })
    await waitFor(() => expect(button.disabled).toBe(false))
    fireEvent.click(button)

    const posts = tryOnPosts(calls)
    await waitFor(() => expect(posts).toHaveLength(1))
    expect(JSON.parse(posts[0].options.body)).toEqual({ garment_ids: [11, 22, 33] })

    expect(await screen.findByAltText('Try-on result')).toBeTruthy()
  })
})