import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowLeft, RefreshCw } from 'lucide-react'

import { API_BASE, toImageUrl } from '../utils/api'
import Settings from '../components/Settings'
import TryOnDialog from '../components/TryOnDialog'
import useTryOn from '../hooks/useTryOn'

export default function ClothesDetail() {
    const { t } = useTranslation()
    const navigate = useNavigate()
    const { id } = useParams()
    const [item, setItem] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [settingsOpen, setSettingsOpen] = useState(false)
    const [tryOnOpen, setTryOnOpen] = useState(false)

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
        fetchClothesDetail()
    }, [id])

    const fetchClothesDetail = async () => {
        setLoading(true)
        setError('')
        try {
            const response = await fetch(`${API_BASE}/clothes/${id}`)
            if (!response.ok) {
                throw new Error(response.status === 404 ? 'NOT_FOUND' : 'FETCH_FAILED')
            }
            const data = await response.json()
            setItem(data)
        } catch (err) {
            setItem(null)
            setError(err.message || 'FETCH_FAILED')
        } finally {
            setLoading(false)
        }
    }

    const renderTags = (values) => {
        if (!Array.isArray(values) || values.length === 0) {
            return <span className="text-sm text-zinc-400">{t('clothesDetail.empty')}</span>
        }
        return (
            <div className="flex flex-wrap gap-2">
                {values.map(value => (
                    <span key={value} className="liquid-chip !py-1 text-xs">
                        {value}
                    </span>
                ))}
            </div>
        )
    }

    const handleGenerateTryOn = () => {
        if (!item) return
        setTryOnOpen(true)
        if (hasPersonImage) {
            void generate([item.id])
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

    if (loading) {
        return (
            <div className="min-h-screen flex flex-col items-center justify-center">
                <div className="w-10 h-10 border-4 border-zinc-200 dark:border-zinc-700 border-t-accent rounded-full animate-spin"></div>
                <p className="mt-4 text-sm text-zinc-500">{t('clothesDetail.loading')}</p>
            </div>
        )
    }

    if (!item || error) {
        return (
            <div className="min-h-screen p-4">
                <header className="glass-header px-4 py-4 -mx-4">
                    <button className="btn-icon" onClick={() => navigate('/wardrobe')}>
                        <ArrowLeft size={22} />
                    </button>
                </header>
                <div className="mt-8 card p-6 text-center space-y-4">
                    <p className="text-sm text-zinc-500">
                        {error === 'NOT_FOUND' ? t('clothesDetail.notFound') : t('clothesDetail.loadFailed')}
                    </p>
                    <button className="btn-secondary mx-auto" onClick={fetchClothesDetail}>
                        <RefreshCw size={16} />
                        {t('clothesDetail.retry')}
                    </button>
                </div>
            </div>
        )
    }

    return (
        <div className="min-h-screen pb-8 animate-fade-in">
            <header className="glass-header px-4 py-4 sticky top-0">
                <div className="flex items-center gap-2">
                    <button className="btn-icon" onClick={() => navigate('/wardrobe')}>
                        <ArrowLeft size={22} />
                    </button>
                    <h1 className="text-xl font-serif font-semibold text-[var(--text-primary)]">{t('clothesDetail.title')}</h1>
                </div>
            </header>

            <div className="p-4 sm:px-6 lg:px-8 space-y-4 max-w-6xl mx-auto w-full lg:grid lg:grid-cols-12 lg:gap-4 lg:space-y-0">
                <article className="card overflow-hidden lg:col-span-5">
                    <div className="media-tile aspect-square p-6 flex items-center justify-center">
                        <img
                            src={toImageUrl(item.image_url)}
                            alt={item.item}
                            className="w-full h-full object-contain drop-shadow-md"
                        />
                    </div>
                    <div className="p-4 border-t border-[var(--line)]">
                        <h2 className="text-lg font-semibold text-[var(--text-primary)]">{item.item}</h2>
                        <p className="text-sm text-zinc-500 mt-1">{item.category}</p>
                    </div>
                </article>

                <section className="card p-4 space-y-4 lg:col-span-7">
                    <div>
                        <h3 className="text-sm font-medium text-zinc-500">{t('clothesDetail.description')}</h3>
                        <p className="mt-1 text-sm text-zinc-800 dark:text-zinc-200">{item.description || t('clothesDetail.empty')}</p>
                    </div>

                    <div>
                        <h3 className="text-sm font-medium text-zinc-500">{t('clothesDetail.color')}</h3>
                        <p className="mt-1 text-sm text-zinc-800 dark:text-zinc-200">{item.color_semantics || t('clothesDetail.empty')}</p>
                    </div>

                    <div>
                        <h3 className="text-sm font-medium text-zinc-500">{t('clothesDetail.style')}</h3>
                        <div className="mt-1">{renderTags(item.style_semantics)}</div>
                    </div>

                    <div>
                        <h3 className="text-sm font-medium text-zinc-500">{t('clothesDetail.season')}</h3>
                        <div className="mt-1">{renderTags(item.season_semantics)}</div>
                    </div>

                    <div>
                        <h3 className="text-sm font-medium text-zinc-500">{t('clothesDetail.usage')}</h3>
                        <div className="mt-1">{renderTags(item.usage_semantics)}</div>
                    </div>
                </section>

                <section className="card p-4 space-y-4 lg:col-span-12">
                    <div>
                        <h3 className="text-sm font-medium text-zinc-500">{t('clothesDetail.tryOnTitle')}</h3>
                        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-300">{t('clothesDetail.tryOnHint')}</p>
                    </div>

                    <div>
                        <button
                            className="btn-primary"
                            type="button"
                            onClick={handleGenerateTryOn}
                            disabled={generating || !statusLoaded}
                        >
                            {generating ? t('clothesDetail.tryOnGenerating') : t('clothesDetail.tryOnGenerate')}
                        </button>
                    </div>
                </section>
            </div>

            <Settings isOpen={settingsOpen} onClose={handleCloseSettings} />

            <TryOnDialog
                open={tryOnOpen}
                phase={tryOnPhase}
                resultUrl={resultUrl}
                error={tryOnError}
                onClose={() => setTryOnOpen(false)}
                onOpenSettings={handleOpenSettings}
                onRetry={() => generate([item.id])}
            />
        </div>
    )
}
