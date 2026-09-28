import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Check, Loader2, RefreshCw, Sparkles, X } from 'lucide-react'
import { API_BASE, toImageUrl } from '../utils/api'

const CATEGORIES = ['top', 'bottom', 'shoes', 'accessory']

const CATEGORY_LABEL_KEY = {
    top: 'entry.categoryTop',
    bottom: 'entry.categoryBottom',
    shoes: 'entry.categoryShoes',
    accessory: 'entry.categoryAccessory'
}

const STATUS_CLASS = {
    pending: 'text-zinc-500',
    generating: 'text-accent',
    done: 'text-green-600 dark:text-green-400',
    fallback: 'text-amber-600 dark:text-amber-400',
    failed: 'text-red-600 dark:text-red-400'
}

export default function GarmentReview({ data, onDone, onCancel }) {
    const { t } = useTranslation()
    const [garments, setGarments] = useState([])
    const [committing, setCommitting] = useState(false)
    const [generatingAll, setGeneratingAll] = useState(false)

    useEffect(() => {
        if (!data?.garments) return
        setGarments(data.garments.map(garment => ({
            ...garment,
            selected: true,
            status: garment.status || 'pending',
            generatedUrl: garment.generated_url || '',
            alphaUrl: garment.alpha_url || '',
            error: garment.error || ''
        })))
    }, [data])

    const updateGarment = useCallback((key, patch) => {
        setGarments(prev => prev.map(garment => (
            garment.garment_key === key ? { ...garment, ...patch } : garment
        )))
    }, [])

    const generateOne = useCallback(async (key) => {
        updateGarment(key, { status: 'generating', error: '' })
        try {
            const response = await fetch(`${API_BASE}/capture/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: data.session_id, garment_key: key })
            })
            const body = await response.json().catch(() => ({}))
            if (!response.ok) {
                throw new Error(body.detail || 'GENERATE_FAILED')
            }
            updateGarment(key, {
                status: body.status || 'failed',
                generatedUrl: body.generated_url || '',
                alphaUrl: body.alpha_url || '',
                error: body.error || ''
            })
            return body
        } catch (error) {
            updateGarment(key, { status: 'failed', error: error?.message || 'GENERATE_FAILED' })
            return null
        }
    }, [data, updateGarment])

    const handleGenerateAll = async () => {
        setGeneratingAll(true)
        try {
            for (const garment of garments) {
                await generateOne(garment.garment_key)
            }
        } finally {
            setGeneratingAll(false)
        }
    }

    const handleCommit = async () => {
        const items = garments
            .filter(garment => garment.selected)
            .map(garment => ({
                garment_key: garment.garment_key,
                category: garment.category,
                item: garment.item,
                description: garment.description || '',
                selected: true
            }))

        if (items.length === 0) return

        setCommitting(true)
        try {
            const response = await fetch(`${API_BASE}/capture/commit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: data.session_id, items })
            })
            const body = await response.json().catch(() => ({}))
            if (!response.ok) {
                throw new Error(body.detail || 'COMMIT_FAILED')
            }
            const created = body.created || []
            window.dispatchEvent(new CustomEvent('show-toast', {
                detail: { type: 'success', message: t('capture.commitSuccess', { count: created.length }) }
            }))
            onDone?.(created)
        } catch {
            window.dispatchEvent(new CustomEvent('show-toast', {
                detail: { type: 'error', message: t('capture.commitFailed') }
            }))
        } finally {
            setCommitting(false)
        }
    }

    const renderStatus = (garment) => {
        const key = `capture.status_${garment.status}`
        const text = t(key)
        return (
            <span className={`text-xs font-medium ${STATUS_CLASS[garment.status] || STATUS_CLASS.pending}`}>
                {garment.status === 'generating' && <Loader2 size={12} className="inline animate-spin mr-1" />}
                {garment.status === 'done' && <Check size={12} className="inline mr-1" />}
                {text}
                {garment.status === 'failed' && garment.error ? ` · ${garment.error}` : ''}
            </span>
        )
    }

    const preview = (garment) => garment.alphaUrl || garment.generatedUrl || garment.crop_url

    return (
        <div className="w-full space-y-4 animate-fade-in">
            <div className="card p-4 flex items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                    {data?.source_image && (
                        <img
                            src={toImageUrl(data.source_image)}
                            alt="source"
                            className="w-12 h-12 rounded-lg object-cover shrink-0"
                        />
                    )}
                    <div className="min-w-0">
                        <h3 className="font-semibold text-[var(--text-primary)] truncate">{t('capture.reviewTitle')}</h3>
                        <p className="text-xs text-[var(--text-secondary)]">
                            {t('capture.reviewSubtitle', { count: garments.length })}
                        </p>
                    </div>
                </div>
                <button className="btn-icon" onClick={onCancel} aria-label={t('capture.cancel')}>
                    <X size={18} />
                </button>
            </div>

            {garments.length === 0 && (
                <div className="card p-6 text-center text-sm text-[var(--text-secondary)]">
                    {t('capture.noneDetected')}
                </div>
            )}

            <div className="space-y-3">
                {garments.map(garment => (
                    <div key={garment.garment_key} className="card p-4 space-y-3">
                        <div className="flex gap-3">
                            <div className="w-20 h-20 rounded-lg overflow-hidden liquid-glass shrink-0 flex items-center justify-center">
                                {preview(garment) ? (
                                    <img src={toImageUrl(preview(garment))} alt={garment.item} className="w-full h-full object-contain" />
                                ) : (
                                    <Sparkles size={18} className="text-zinc-400" />
                                )}
                            </div>

                            <div className="flex-1 min-w-0 space-y-2">
                                <div className="flex items-center justify-between gap-2">
                                    <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                                        <input
                                            type="checkbox"
                                            checked={garment.selected}
                                            onChange={e => updateGarment(garment.garment_key, { selected: e.target.checked })}
                                        />
                                        {t('capture.select')}
                                    </label>
                                    {renderStatus(garment)}
                                </div>

                                <input
                                    type="text"
                                    className="input-field !py-1.5 text-sm"
                                    value={garment.item}
                                    onChange={e => updateGarment(garment.garment_key, { item: e.target.value })}
                                    placeholder={t('entry.namePlaceholder')}
                                />

                                <select
                                    className="input-field !py-1.5 text-sm appearance-none"
                                    value={garment.category}
                                    onChange={e => updateGarment(garment.garment_key, { category: e.target.value })}
                                >
                                    {CATEGORIES.map(category => (
                                        <option key={category} value={category}>{t(CATEGORY_LABEL_KEY[category])}</option>
                                    ))}
                                </select>
                            </div>
                        </div>

                        <div className="flex gap-2">
                            <button
                                className="btn-secondary flex-1 !py-1.5 text-xs"
                                onClick={() => generateOne(garment.garment_key)}
                                disabled={garment.status === 'generating' || committing}
                            >
                                {garment.status === 'generating'
                                    ? <Loader2 size={14} className="animate-spin" />
                                    : <RefreshCw size={14} />}
                                {garment.status === 'pending' ? t('capture.generate') : t('capture.regenerate')}
                            </button>
                        </div>
                    </div>
                ))}
            </div>

            {garments.length > 0 && (
                <div className="flex flex-col sm:flex-row gap-2">
                    <button
                        className="btn-secondary flex-1"
                        onClick={handleGenerateAll}
                        disabled={generatingAll || committing}
                    >
                        {generatingAll ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
                        {t('capture.generateAll')}
                    </button>
                    <button
                        className="btn-primary flex-1"
                        onClick={handleCommit}
                        disabled={committing || generatingAll || garments.every(garment => !garment.selected)}
                    >
                        {committing ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />}
                        {t('capture.commit')}
                    </button>
                </div>
            )}
        </div>
    )
}