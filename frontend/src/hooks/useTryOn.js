import { useCallback, useEffect, useState } from 'react'

import { API_BASE, toImageUrl } from '../utils/api'

/**
 * 统一的 AI 试穿逻辑：读取本人照片状态 + 调用 /api/tryon 生成试穿图。
 * 详情页与穿搭页共用。
 */
export default function useTryOn() {
    const [hasPersonImage, setHasPersonImage] = useState(false)
    const [personImageUrl, setPersonImageUrl] = useState('')
    const [statusLoaded, setStatusLoaded] = useState(false)
    const [generating, setGenerating] = useState(false)
    const [resultUrl, setResultUrl] = useState('')
    const [error, setError] = useState('')

    const refreshPersonStatus = useCallback(async (signal) => {
        try {
            const response = await fetch(`${API_BASE}/config`, { signal })
            if (!response.ok) return
            const data = await response.json()
            setHasPersonImage(Boolean(data.has_person_image))
            setPersonImageUrl(data.person_image_url || '')
        } catch (err) {
            if (err.name !== 'AbortError') {
                console.error('Failed to fetch try-on person status:', err)
            }
        } finally {
            if (!signal?.aborted) {
                setStatusLoaded(true)
            }
        }
    }, [])

    useEffect(() => {
        const controller = new AbortController()
        void refreshPersonStatus(controller.signal)
        return () => controller.abort()
    }, [refreshPersonStatus])

    const generate = useCallback(async (garmentIds) => {
        const ids = (garmentIds || []).filter((id) => typeof id === 'number')
        if (!ids.length) {
            setError('NO_GARMENTS')
            return false
        }

        setGenerating(true)
        setError('')
        setResultUrl('')
        try {
            const response = await fetch(`${API_BASE}/tryon`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ garment_ids: ids })
            })
            const data = await response.json().catch(() => ({}))
            if (!response.ok || !data.result_image_url) {
                const detail = data.detail === 'PERSON_IMAGE_MISSING'
                    ? 'PERSON_IMAGE_MISSING'
                    : (data.detail || 'TRYON_FAILED')
                throw new Error(detail)
            }
            setResultUrl(toImageUrl(data.result_image_url))
            return true
        } catch (err) {
            setError(err.message || 'TRYON_FAILED')
            return false
        } finally {
            setGenerating(false)
        }
    }, [])

    const reset = useCallback(() => {
        setResultUrl('')
        setError('')
    }, [])

    return {
        hasPersonImage,
        personImageUrl,
        statusLoaded,
        generating,
        resultUrl,
        error,
        refreshPersonStatus,
        generate,
        reset
    }
}