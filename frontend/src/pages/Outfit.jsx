import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ChevronLeft, ChevronRight, Shuffle } from 'lucide-react'

import { API_BASE, toImageUrl } from '../utils/api'
import OutfitCanvas from '../components/OutfitCanvas'
import Settings from '../components/Settings'
import TryOnDialog from '../components/TryOnDialog'
import useTryOn from '../hooks/useTryOn'

const CATEGORIES = [
    { key: 'tops', labelKey: 'outfit.top' },
    { key: 'bottoms', labelKey: 'outfit.bottom' },
    { key: 'shoes', labelKey: 'outfit.shoes' }
]

export default function Outfit() {
    const navigate = useNavigate()
    const { t } = useTranslation()
    const [wardrobe, setWardrobe] = useState({ tops: [], bottoms: [], shoes: [], accessories: [] })
    const [loading, setLoading] = useState(true)
    const [filterSeason, setFilterSeason] = useState('all')

    const [currentIndices, setCurrentIndices] = useState({
        tops: 0,
        bottoms: 0,
        shoes: 0
    })

    const [transforms, setTransforms] = useState({ tops: null, bottoms: null, shoes: null })
    const [selectedCategory, setSelectedCategory] = useState(null)
    const [settingsOpen, setSettingsOpen] = useState(false)
    const [tryOnOpen, setTryOnOpen] = useState(false)
    const previousItemIds = useRef({ tops: null, bottoms: null, shoes: null })

    const {
        hasPersonImage,
        statusLoaded,
        generating,
        resultUrl,
        error: tryOnError,
        refreshPersonStatus,
        generate
    } = useTryOn()

    useEffect(() => {
        const controller = new AbortController()
        void fetchWardrobe(controller.signal)
        return () => controller.abort()
    }, [])

    const fetchWardrobe = async (signal) => {
        try {
            const response = await fetch(`${API_BASE}/wardrobe`, { signal })
            if (response.ok) {
                const data = await response.json()
                setWardrobe({
                    tops: data.tops || [],
                    bottoms: data.bottoms || [],
                    shoes: data.shoes || [],
                    accessories: data.accessories || []
                })
            }
        } catch (error) {
            if (error.name !== 'AbortError') {
                console.error(error)
            }
        } finally {
            if (!signal?.aborted) {
                setLoading(false)
            }
        }
    }

    const seasonKeywordMap = {
        '春': ['春', 'spring'],
        '夏': ['夏', 'summer'],
        '秋': ['秋', 'autumn', 'fall'],
        '冬': ['冬', 'winter']
    }

    const filterBySeason = (items, category) => {
        if (filterSeason === 'all') return items

        const matched = items.filter(item => {
            const seasons = Array.isArray(item.season_semantics) ? item.season_semantics : []
            if (seasons.length === 0) {
                return category === 'shoes'
            }

            const keywords = seasonKeywordMap[filterSeason] || [filterSeason]
            return seasons.some(season => {
                const normalized = String(season || '').toLowerCase()
                return keywords.some(keyword => normalized.includes(keyword.toLowerCase()))
            })
        })

        if (category === 'shoes' && matched.length === 0 && items.length > 0) {
            return items
        }
        return matched
    }

    const tops = filterBySeason(wardrobe.tops, 'tops')
    const bottoms = filterBySeason(wardrobe.bottoms, 'bottoms')
    const shoes = filterBySeason(wardrobe.shoes, 'shoes')

    useEffect(() => {
        setCurrentIndices(prev => ({
            tops: tops.length > 0 ? Math.min(prev.tops, tops.length - 1) : 0,
            bottoms: bottoms.length > 0 ? Math.min(prev.bottoms, bottoms.length - 1) : 0,
            shoes: shoes.length > 0 ? Math.min(prev.shoes, shoes.length - 1) : 0
        }))
    }, [tops.length, bottoms.length, shoes.length])

    const getItemsByCategory = (category) => {
        if (category === 'tops') return tops
        if (category === 'bottoms') return bottoms
        return shoes
    }

    const getCurrentItem = (category) => {
        const items = getItemsByCategory(category)
        if (!items.length) return null
        return items[currentIndices[category]] || items[0]
    }

    const currentItemIds = {
        tops: getCurrentItem('tops')?.id ?? null,
        bottoms: getCurrentItem('bottoms')?.id ?? null,
        shoes: getCurrentItem('shoes')?.id ?? null
    }

    // 切换衣物（轮播 / 随机 / 季节筛选）后，该类别的手动摆位复位
    useEffect(() => {
        const previous = previousItemIds.current
        const changed = Object.keys(currentItemIds).filter(
            (category) => previous[category] !== currentItemIds[category]
        )
        previousItemIds.current = currentItemIds

        if (changed.length === 0) return
        setTransforms(prev => {
            const next = { ...prev }
            changed.forEach((category) => { next[category] = null })
            return next
        })
        setSelectedCategory(prev => (prev && changed.includes(prev) ? null : prev))
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [currentItemIds.tops, currentItemIds.bottoms, currentItemIds.shoes])

    const handleTransformChange = (category, next) => {
        setTransforms(prev => ({ ...prev, [category]: next }))
    }

    const shiftCategory = (category, direction) => {
        const items = getItemsByCategory(category)
        if (items.length <= 1) return

        setCurrentIndices(prev => {
            const currentIndex = prev[category]
            const nextIndex = direction === 'prev'
                ? (currentIndex > 0 ? currentIndex - 1 : items.length - 1)
                : (currentIndex < items.length - 1 ? currentIndex + 1 : 0)
            return { ...prev, [category]: nextIndex }
        })
    }

    const shuffleOutfit = () => {
        setCurrentIndices({
            tops: tops.length > 0 ? Math.floor(Math.random() * tops.length) : 0,
            bottoms: bottoms.length > 0 ? Math.floor(Math.random() * bottoms.length) : 0,
            shoes: shoes.length > 0 ? Math.floor(Math.random() * shoes.length) : 0
        })
    }

    const seasonFilters = [
        { key: 'all', label: t('outfit.allSeasons') },
        { key: '春', label: t('filter.spring') },
        { key: '夏', label: t('filter.summer') },
        { key: '秋', label: t('filter.autumn') },
        { key: '冬', label: t('filter.winter') }
    ]

    if (loading) return (
        <div className="flex flex-col items-center justify-center min-h-[60vh]">
            <div className="w-10 h-10 border-4 border-zinc-200 dark:border-zinc-700 border-t-accent rounded-full animate-spin"></div>
        </div>
    )

    const topItem = getCurrentItem('tops')
    const bottomItem = getCurrentItem('bottoms')
    const shoesItem = getCurrentItem('shoes')

    const tryOnGarmentIds = [topItem, bottomItem, shoesItem].filter(Boolean).map(item => item.id)
    const canGenerate = tryOnGarmentIds.length > 0

    const handleGenerateTryOn = () => {
        if (!canGenerate) return
        setTryOnOpen(true)
        if (hasPersonImage) {
            void generate(tryOnGarmentIds)
        }
    }

    const handleOpenSettings = () => {
        setTryOnOpen(false)
        setSettingsOpen(true)
    }

    const handleCloseSettings = () => {
        setSettingsOpen(false)
        void refreshPersonStatus()
    }

    const tryOnPhase = !hasPersonImage
        ? 'gate'
        : generating
            ? 'generating'
            : tryOnError
                ? 'error'
                : 'result'

    return (
        <div className="px-3 sm:px-4 lg:px-0 pt-3 pb-2 flex flex-col max-w-6xl mx-auto w-full">
            <header className="shrink-0 mb-3">
                <div className="flex items-center justify-between mb-2">
                    <h2 className="text-[22px] font-serif font-bold tracking-tight text-[var(--text-primary)]">{t('outfit.title')}</h2>
                    <button
                        className="btn-icon"
                        onClick={shuffleOutfit}
                        title={t('outfit.shuffle')}
                    >
                        <Shuffle size={18} className="group-active:-rotate-90 transition-transform duration-300" />
                    </button>
                </div>

                <div className="flex gap-1.5 overflow-x-auto hide-scrollbar pb-0.5">
                    {seasonFilters.map(s => (
                        <button
                            key={s.key}
                            className={`px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap transition-all duration-300 ${
                                filterSeason === s.key
                                    ? 'liquid-chip liquid-chip-active'
                                    : 'liquid-chip'
                                }`}
                            onClick={() => setFilterSeason(s.key)}
                        >
                            {s.label}
                        </button>
                    ))}
                </div>
            </header>

            <div className="grid gap-3 lg:grid-cols-12">
                <section className="card lg:col-span-7 overflow-hidden flex flex-col">
                    <div className="p-3 sm:p-4 flex-1 flex flex-col min-h-0">
                        <div className="liquid-panel rounded-[28px] overflow-hidden p-2 sm:p-3 flex-1 min-h-0">
                            <OutfitCanvas
                                items={{ tops: topItem, bottoms: bottomItem, shoes: shoesItem }}
                                transforms={transforms}
                                selected={selectedCategory}
                                onSelect={setSelectedCategory}
                                onTransformChange={handleTransformChange}
                            />
                        </div>
                        <div className="pt-3">
                            <button
                                className="btn-primary w-full"
                                type="button"
                                onClick={handleGenerateTryOn}
                                disabled={!canGenerate || generating || !statusLoaded}
                            >
                                {generating ? t('outfit.tryOnGenerating') : t('outfit.generateTryOn')}
                            </button>
                        </div>
                    </div>
                </section>

                <aside className="lg:col-span-5 grid grid-cols-1 gap-3">
                    {CATEGORIES.map((category) => {
                        const items = getItemsByCategory(category.key)
                        const item = getCurrentItem(category.key)
                        const currentIndex = currentIndices[category.key] || 0
                        return (
                            <article key={category.key} className="card p-3">
                                <div className="flex items-center justify-between gap-2 mb-2">
                                    <div className="text-xs text-zinc-500 uppercase tracking-wide">{t(category.labelKey)}</div>
                                    <div className="flex items-center gap-1.5">
                                        <button
                                            className="btn-icon disabled:opacity-40"
                                            onClick={() => shiftCategory(category.key, 'prev')}
                                            disabled={items.length <= 1}
                                            type="button"
                                        >
                                            <ChevronLeft size={15} />
                                        </button>
                                        <span className="text-xs text-zinc-500 min-w-[3rem] text-center">
                                            {items.length ? `${currentIndex + 1}/${items.length}` : '--'}
                                        </span>
                                        <button
                                            className="btn-icon disabled:opacity-40"
                                            onClick={() => shiftCategory(category.key, 'next')}
                                            disabled={items.length <= 1}
                                            type="button"
                                        >
                                            <ChevronRight size={15} />
                                        </button>
                                    </div>
                                </div>

                                <button
                                    className="media-tile w-full h-40 lg:h-44 p-2.5 flex items-center justify-center hover:opacity-90 transition-opacity"
                                    onClick={() => item && navigate(`/clothes/${item.id}`)}
                                    type="button"
                                    disabled={!item}
                                >
                                    {item ? (
                                        <img
                                            src={toImageUrl(item.image_url)}
                                            alt={item.item}
                                            className="w-full h-full object-contain"
                                        />
                                    ) : (
                                        <span className="text-xs text-zinc-400 text-center">{t('outfit.noItems', { label: t(category.labelKey) })}</span>
                                    )}
                                </button>
                            </article>
                        )
                    })}
                </aside>
            </div>

            <Settings isOpen={settingsOpen} onClose={handleCloseSettings} />

            <TryOnDialog
                open={tryOnOpen}
                phase={tryOnPhase}
                resultUrl={resultUrl}
                error={tryOnError}
                onClose={() => setTryOnOpen(false)}
                onOpenSettings={handleOpenSettings}
                onRetry={() => generate(tryOnGarmentIds)}
            />
        </div>
    )
}
