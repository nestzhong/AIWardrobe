import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import i18n from '../i18n'
import { ThemeProvider } from '../contexts/ThemeContext'
import Outfit from '../pages/Outfit'

// jsdom 不一定实现 PointerEvent，补一个最小实现让 fireEvent 能带 clientX / pointerId
if (!window.PointerEvent) {
  window.PointerEvent = class PointerEvent extends MouseEvent {}
}

const wardrobeResponse = {
  tops: [{ id: 1, item: 'Jacket', image_url: '/uploads/jacket.png', season_semantics: [] }],
  bottoms: [{ id: 2, item: 'Pants', image_url: '/uploads/pants.png', season_semantics: [] }],
  shoes: [{ id: 3, item: 'Sneakers', image_url: '/uploads/shoes.png', season_semantics: [] }],
  accessories: [],
}

const renderOutfit = () => render(
  <ThemeProvider>
    <MemoryRouter>
      <Outfit />
    </MemoryRouter>
  </ThemeProvider>,
)

describe('Outfit canvas interactions', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    i18n.changeLanguage('en')
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    })
    vi.stubGlobal('fetch', vi.fn(async (url) => {
      if (String(url).endsWith('/wardrobe')) {
        return { ok: true, json: async () => wardrobeResponse }
      }
      return { ok: false, json: async () => ({}) }
    }))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders one draggable layer per garment and an enabled try-on button', async () => {
    renderOutfit()

    const layers = await waitFor(() => {
      const found = document.querySelectorAll('[data-outfit-layer]')
      expect(found.length).toBe(3)
      return found
    })

    expect(layers[0].getAttribute('data-category')).toBe('tops')

    const tryOnButton = screen.getByRole('button', { name: 'Generate try-on' })
    await waitFor(() => expect(tryOnButton.disabled).toBe(false))
  })

  it('selects a garment on click and shows the editing toolbar', async () => {
    renderOutfit()

    const topLayer = await waitFor(() => {
      const found = document.querySelector('[data-category="tops"]')
      expect(found).toBeTruthy()
      return found
    })

    expect(screen.queryByRole('button', { name: 'Zoom in' })).toBeNull()

    fireEvent.pointerDown(topLayer, { pointerId: 1, pointerType: 'mouse', button: 0, clientX: 100, clientY: 100 })

    expect(await screen.findByRole('button', { name: 'Zoom in' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Reset' })).toBeTruthy()
  })

  it('drags a selected garment and updates its offset', async () => {
    renderOutfit()

    const topLayer = await waitFor(() => {
      const found = document.querySelector('[data-category="tops"]')
      expect(found).toBeTruthy()
      return found
    })
    const wrapper = topLayer.parentElement

    fireEvent.pointerDown(topLayer, { pointerId: 2, pointerType: 'mouse', button: 0, clientX: 100, clientY: 100 })
    fireEvent.pointerMove(topLayer, { pointerId: 2, pointerType: 'mouse', clientX: 140, clientY: 130 })
    fireEvent.pointerUp(topLayer, { pointerId: 2, pointerType: 'mouse', clientX: 140, clientY: 130 })

    expect(wrapper.style.transform).toContain('translate(40px, 30px)')
  })

  it('zooms and rotates the selected garment from the toolbar', async () => {
    renderOutfit()

    const topLayer = await waitFor(() => {
      const found = document.querySelector('[data-category="tops"]')
      expect(found).toBeTruthy()
      return found
    })

    fireEvent.pointerDown(topLayer, { pointerId: 3, pointerType: 'mouse', button: 0, clientX: 100, clientY: 100 })

    fireEvent.click(await screen.findByRole('button', { name: 'Zoom in' }))
    expect(topLayer.style.transform).toContain('scale(1.15)')

    fireEvent.click(screen.getByRole('button', { name: 'Rotate right' }))
    expect(topLayer.style.transform).toContain('rotate(90deg)')
  })

  it('resets the selected garment transform', async () => {
    renderOutfit()

    const topLayer = await waitFor(() => {
      const found = document.querySelector('[data-category="tops"]')
      expect(found).toBeTruthy()
      return found
    })

    fireEvent.pointerDown(topLayer, { pointerId: 4, pointerType: 'mouse', button: 0, clientX: 100, clientY: 100 })
    fireEvent.click(await screen.findByRole('button', { name: 'Zoom in' }))
    expect(topLayer.style.transform).toContain('scale(1.15)')

    fireEvent.click(screen.getByRole('button', { name: 'Reset' }))
    expect(topLayer.style.transform).toContain('scale(1)')
  })
})