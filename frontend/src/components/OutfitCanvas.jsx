import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { RotateCcw, RotateCw, ZoomIn, ZoomOut, Undo2 } from 'lucide-react'

import { toImageUrl } from '../utils/api'

const DEFAULT_TRANSFORM = { x: 0, y: 0, scale: 1, rotate: 0 }

const MIN_SCALE = 0.3
const MAX_SCALE = 4
const ROTATE_SNAP_STEP = 15

// 默认叠放摆位（相对画布的百分比），复刻原来的“上/中/下”三宫格观感
const SLOT_PRESETS = {
    tops: { left: 50, top: 27, width: 42, height: 38, labelKey: 'outfit.top' },
    bottoms: { left: 50, top: 60, width: 34, height: 31, labelKey: 'outfit.bottom' },
    shoes: { left: 50, top: 85, width: 28, height: 19, labelKey: 'outfit.shoes' }
}

const SLOT_ORDER = ['tops', 'bottoms', 'shoes']

const clamp = (value, min, max) => Math.min(max, Math.max(min, value))

const toDegrees = (radians) => (radians * 180) / Math.PI

const angleBetween = (center, point) => toDegrees(Math.atan2(point.y - center.y, point.x - center.x))

const distanceBetween = (a, b) => Math.hypot(a.x - b.x, a.y - b.y)

const snapAngle = (angle) => Math.round(angle / ROTATE_SNAP_STEP) * ROTATE_SNAP_STEP

export default function OutfitCanvas({ items, transforms, selected, onSelect, onTransformChange }) {
    const { t } = useTranslation()
    const containerRef = useRef(null)
    const layerRefs = useRef({})
    const gestureRef = useRef(null)

    const getTransform = (category) => ({ ...DEFAULT_TRANSFORM, ...(transforms?.[category] || {}) })

    const commit = (category, next, gesture) => {
        if (gesture) {
            gesture.live = next
        }
        onTransformChange(category, next)
    }

    const centerOf = (category) => {
        const layer = layerRefs.current[category]
        if (!layer) return null
        const rect = layer.getBoundingClientRect()
        return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 }
    }

    const beginGesture = (event, category) => {
        if (event.pointerType === 'mouse' && event.button !== 0) return
        event.preventDefault()
        event.stopPropagation()
        onSelect(category)

        const layer = event.currentTarget
        layer.setPointerCapture?.(event.pointerId)

        gestureRef.current = {
            category,
            mode: 'transform',
            pointers: new Map([[event.pointerId, { x: event.clientX, y: event.clientY }]]),
            live: getTransform(category),
            dragStart: {
                pointer: { x: event.clientX, y: event.clientY },
                transform: getTransform(category)
            },
            pinch: null
        }
    }

    const beginHandleGesture = (event, category, mode) => {
        if (event.pointerType === 'mouse' && event.button !== 0) return
        event.preventDefault()
        event.stopPropagation()
        onSelect(category)

        const handle = event.currentTarget
        handle.setPointerCapture?.(event.pointerId)

        const center = centerOf(category)
        if (!center) return

        const transform = getTransform(category)
        const pointer = { x: event.clientX, y: event.clientY }

        gestureRef.current = {
            category,
            mode,
            center,
            live: transform,
            startDistance: Math.max(distanceBetween(pointer, center), 1),
            startAngle: angleBetween(center, pointer),
            startTransform: transform
        }
    }

    const handleTransformMove = (event, category) => {
        const gesture = gestureRef.current
        if (!gesture || gesture.category !== category || gesture.mode !== 'transform') return
        event.preventDefault()
        event.stopPropagation()

        const pointer = { x: event.clientX, y: event.clientY }
        gesture.pointers.set(event.pointerId, pointer)

        if (gesture.pointers.size >= 2) {
            const [first, second] = [...gesture.pointers.values()]
            const distance = Math.max(distanceBetween(first, second), 1)
            const angle = angleBetween(first, second)

            if (!gesture.pinch) {
                gesture.pinch = { distance, angle, transform: gesture.live }
                gesture.dragStart = null
            }

            const scale = clamp(
                gesture.pinch.transform.scale * (distance / gesture.pinch.distance),
                MIN_SCALE,
                MAX_SCALE
            )
            const rotate = gesture.pinch.transform.rotate + (angle - gesture.pinch.angle)
            commit(category, { ...gesture.pinch.transform, scale, rotate }, gesture)
            return
        }

        if (!gesture.dragStart) return
        const preset = SLOT_PRESETS[category]
        const container = containerRef.current
        let dx = pointer.x - gesture.dragStart.pointer.x
        let dy = pointer.y - gesture.dragStart.pointer.y

        if (container && preset) {
            const rect = container.getBoundingClientRect()
            if (rect.width > 0 && rect.height > 0) {
                const anchorX = (preset.left / 100) * rect.width
                const anchorY = (preset.top / 100) * rect.height
                const centerX = clamp(anchorX + gesture.dragStart.transform.x + dx, 4, rect.width - 4)
                const centerY = clamp(anchorY + gesture.dragStart.transform.y + dy, 4, rect.height - 4)
                dx = centerX - anchorX - gesture.dragStart.transform.x
                dy = centerY - anchorY - gesture.dragStart.transform.y
            }
        }

        commit(category, {
            ...gesture.dragStart.transform,
            x: gesture.dragStart.transform.x + dx,
            y: gesture.dragStart.transform.y + dy
        }, gesture)
    }

    const handleRotateMove = (event) => {
        const gesture = gestureRef.current
        if (!gesture || gesture.mode !== 'rotate') return
        event.preventDefault()
        event.stopPropagation()

        const pointer = { x: event.clientX, y: event.clientY }
        const angle = angleBetween(gesture.center, pointer)
        let rotate = gesture.startTransform.rotate + (angle - gesture.startAngle)
        if (event.shiftKey) {
            rotate = snapAngle(rotate)
        }
        commit(gesture.category, { ...gesture.startTransform, rotate }, gesture)
    }

    const handleScaleMove = (event) => {
        const gesture = gestureRef.current
        if (!gesture || gesture.mode !== 'scale') return
        event.preventDefault()
        event.stopPropagation()

        const pointer = { x: event.clientX, y: event.clientY }
        const distance = distanceBetween(pointer, gesture.center)
        const scale = clamp(
            gesture.startTransform.scale * (distance / gesture.startDistance),
            MIN_SCALE,
            MAX_SCALE
        )
        commit(gesture.category, { ...gesture.startTransform, scale }, gesture)
    }

    const endGesture = (event) => {
        const gesture = gestureRef.current
        if (!gesture) return
        event.stopPropagation()
        event.currentTarget.releasePointerCapture?.(event.pointerId)
        gestureRef.current = null
    }

    const handleLayerPointerUp = (event, category) => {
        const gesture = gestureRef.current
        if (!gesture || gesture.category !== category || gesture.mode !== 'transform') return
        event.stopPropagation()
        gesture.pointers.delete(event.pointerId)
        event.currentTarget.releasePointerCapture?.(event.pointerId)

        if (gesture.pointers.size === 1) {
            const [remaining] = [...gesture.pointers.values()]
            gesture.pinch = null
            gesture.dragStart = { pointer: remaining, transform: gesture.live }
            return
        }

        if (gesture.pointers.size === 0) {
            gestureRef.current = null
        }
    }

    // 滚轮缩放：需要在原生监听器里 preventDefault，React 的 onWheel 默认是 passive
    useEffect(() => {
        const container = containerRef.current
        if (!container) return undefined

        const onWheel = (event) => {
            const layer = event.target?.closest?.('[data-outfit-layer]')
            if (!layer) return
            const category = layer.getAttribute('data-category')
            if (!category || selected !== category) return
            event.preventDefault()
            const current = getTransform(category)
            const scale = clamp(current.scale * Math.exp(-event.deltaY * 0.0015), MIN_SCALE, MAX_SCALE)
            onTransformChange(category, { ...current, scale })
        }

        container.addEventListener('wheel', onWheel, { passive: false })
        return () => container.removeEventListener('wheel', onWheel)
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selected, transforms, onTransformChange])

    const rotateBy = (category, delta) => {
        const current = getTransform(category)
        onTransformChange(category, { ...current, rotate: current.rotate + delta })
    }

    const zoomBy = (category, factor) => {
        const current = getTransform(category)
        onTransformChange(category, { ...current, scale: clamp(current.scale * factor, MIN_SCALE, MAX_SCALE) })
    }

    const reset = (category) => {
        onTransformChange(category, { ...DEFAULT_TRANSFORM })
    }

    const hasAnyItem = SLOT_ORDER.some((category) => items?.[category])

    const handleBackgroundPointerDown = (event) => {
        if (event.target === event.currentTarget) {
            onSelect(null)
        }
    }

    return (
        <div
            ref={containerRef}
            className="relative w-full h-full min-h-[360px] overflow-hidden select-none"
            style={{ touchAction: 'pan-y' }}
            onPointerDown={handleBackgroundPointerDown}
        >
            {SLOT_ORDER.map((category) => {
                const preset = SLOT_PRESETS[category]
                const item = items?.[category]
                const transform = getTransform(category)
                const isSelected = selected === category

                if (!item) {
                    return (
                        <span
                            key={`empty-${category}`}
                            className="absolute -translate-x-1/2 -translate-y-1/2 text-xs text-zinc-400"
                            style={{ left: `${preset.left}%`, top: `${preset.top}%` }}
                        >
                            {t('outfit.noItems', { label: t(preset.labelKey) })}
                        </span>
                    )
                }

                return (
                    <div
                        key={category}
                        className="absolute"
                        style={{
                            left: `${preset.left}%`,
                            top: `${preset.top}%`,
                            width: `${preset.width}%`,
                            height: `${preset.height}%`,
                            transform: `translate(-50%, -50%) translate(${transform.x}px, ${transform.y}px)`,
                            zIndex: isSelected ? 30 : 10
                        }}
                    >
                        <div
                            data-outfit-layer
                            data-category={category}
                            ref={(el) => { layerRefs.current[category] = el }}
                            className={`relative w-full h-full cursor-grab active:cursor-grabbing ${
                                isSelected ? 'ring-2 ring-[var(--accent)] rounded-xl' : ''
                            }`}
                            style={{
                                transform: `rotate(${transform.rotate}deg) scale(${transform.scale})`,
                                transformOrigin: 'center',
                                touchAction: 'none'
                            }}
                            onPointerDown={(event) => beginGesture(event, category)}
                            onPointerMove={(event) => handleTransformMove(event, category)}
                            onPointerUp={(event) => handleLayerPointerUp(event, category)}
                            onPointerCancel={(event) => handleLayerPointerUp(event, category)}
                        >
                            <img
                                src={toImageUrl(item.image_url)}
                                alt={item.item}
                                draggable="false"
                                className="w-full h-full object-contain pointer-events-none"
                                onDragStart={(event) => event.preventDefault()}
                            />

                            {isSelected && (
                                <>
                                    <button
                                        type="button"
                                        aria-label={t('outfit.rotate')}
                                        title={t('outfit.rotate')}
                                        className="absolute left-1/2 top-0 w-8 h-8 rounded-full flex items-center justify-center text-[var(--accent)] bg-[var(--glass-surface-strong)] border border-[var(--glass-border)] shadow-md cursor-grab active:cursor-grabbing"
                                        style={{ transform: `translate(-50%, -115%) scale(${1 / transform.scale})`, touchAction: 'none' }}
                                        onPointerDown={(event) => beginHandleGesture(event, category, 'rotate')}
                                        onPointerMove={handleRotateMove}
                                        onPointerUp={endGesture}
                                        onPointerCancel={endGesture}
                                    >
                                        <RotateCw size={15} />
                                    </button>

                                    <button
                                        type="button"
                                        aria-label={t('outfit.resize')}
                                        title={t('outfit.resize')}
                                        className="absolute left-full top-full w-8 h-8 rounded-full flex items-center justify-center text-[var(--accent)] bg-[var(--glass-surface-strong)] border border-[var(--glass-border)] shadow-md cursor-nwse-resize"
                                        style={{ transform: `translate(-50%, -50%) scale(${1 / transform.scale})`, touchAction: 'none' }}
                                        onPointerDown={(event) => beginHandleGesture(event, category, 'scale')}
                                        onPointerMove={handleScaleMove}
                                        onPointerUp={endGesture}
                                        onPointerCancel={endGesture}
                                    >
                                        <ZoomIn size={15} />
                                    </button>
                                </>
                            )}
                        </div>
                    </div>
                )
            })}

            {selected && (
                <div className="absolute bottom-2 left-1/2 -translate-x-1/2 z-40 flex items-center gap-1 liquid-glass rounded-full px-1.5 py-1.5">
                    <button type="button" className="w-9 h-9 rounded-full flex items-center justify-center text-[var(--text-secondary)] hover:text-[var(--accent)] transition-colors" title={t('outfit.rotateLeft')} aria-label={t('outfit.rotateLeft')} onClick={() => rotateBy(selected, -90)}>
                        <RotateCcw size={16} />
                    </button>
                    <button type="button" className="w-9 h-9 rounded-full flex items-center justify-center text-[var(--text-secondary)] hover:text-[var(--accent)] transition-colors" title={t('outfit.rotateRight')} aria-label={t('outfit.rotateRight')} onClick={() => rotateBy(selected, 90)}>
                        <RotateCw size={16} />
                    </button>
                    <button type="button" className="w-9 h-9 rounded-full flex items-center justify-center text-[var(--text-secondary)] hover:text-[var(--accent)] transition-colors" title={t('outfit.zoomOut')} aria-label={t('outfit.zoomOut')} onClick={() => zoomBy(selected, 1 / 1.15)}>
                        <ZoomOut size={16} />
                    </button>
                    <button type="button" className="w-9 h-9 rounded-full flex items-center justify-center text-[var(--text-secondary)] hover:text-[var(--accent)] transition-colors" title={t('outfit.zoomIn')} aria-label={t('outfit.zoomIn')} onClick={() => zoomBy(selected, 1.15)}>
                        <ZoomIn size={16} />
                    </button>
                    <button type="button" className="w-9 h-9 rounded-full flex items-center justify-center text-[var(--text-secondary)] hover:text-[var(--accent)] transition-colors" title={t('outfit.reset')} aria-label={t('outfit.reset')} onClick={() => reset(selected)}>
                        <Undo2 size={16} />
                    </button>
                </div>
            )}

            {!selected && hasAnyItem && (
                <span className="absolute bottom-2 left-1/2 -translate-x-1/2 z-20 text-[11px] text-zinc-400 pointer-events-none">
                    {t('outfit.editHint')}
                </span>
            )}
        </div>
    )
}