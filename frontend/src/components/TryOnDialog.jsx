import { useTranslation } from 'react-i18next'
import { RefreshCw, Sparkles, User } from 'lucide-react'

/**
 * 统一的试穿弹窗：本人照片缺失提示 / 生成中 / 结果 / 失败。
 *
 * @param {boolean} open
 * @param {'gate'|'generating'|'result'|'error'} phase
 * @param {string} resultUrl
 * @param {string} error
 * @param {() => void} onClose
 * @param {() => void} onOpenSettings
 * @param {() => void} onRetry
 */
export default function TryOnDialog({ open, phase, resultUrl, error, onClose, onOpenSettings, onRetry }) {
    const { t } = useTranslation()

    if (!open) return null

    const errorMessage = error === 'PERSON_IMAGE_MISSING'
        ? t('tryOn.missingPersonMessage')
        : error === 'NO_GARMENTS'
            ? t('tryOn.noGarments')
            : (error && error !== 'TRYON_FAILED' ? error : t('tryOn.failed'))

    return (
        <div
            className="fixed inset-0 z-[100] flex items-center justify-center bg-black/35 backdrop-blur-md px-4"
            onClick={onClose}
        >
            <div
                className="liquid-sheet w-full max-w-md rounded-[30px] p-6 space-y-4 animate-fade-in"
                onClick={(event) => event.stopPropagation()}
            >
                {phase === 'gate' && (
                    <>
                        <div className="flex flex-col items-center text-center space-y-2">
                            <div className="w-12 h-12 rounded-full liquid-glass flex items-center justify-center">
                                <User size={22} className="text-accent" />
                            </div>
                            <h3 className="text-lg font-bold text-[var(--text-primary)]">{t('tryOn.missingPersonTitle')}</h3>
                            <p className="text-sm text-zinc-500">{t('tryOn.missingPersonMessage')}</p>
                        </div>
                        <div className="flex gap-2">
                            <button type="button" className="btn-secondary flex-1" onClick={onClose}>
                                {t('tryOn.cancel')}
                            </button>
                            <button type="button" className="btn-primary flex-1" onClick={onOpenSettings}>
                                {t('tryOn.goSettings')}
                            </button>
                        </div>
                    </>
                )}

                {phase === 'generating' && (
                    <div className="flex flex-col items-center text-center space-y-3 py-4">
                        <div className="w-10 h-10 border-4 border-zinc-200 dark:border-zinc-700 border-t-accent rounded-full animate-spin" />
                        <p className="text-sm text-zinc-500">{t('tryOn.generating')}</p>
                    </div>
                )}

                {phase === 'result' && (
                    <>
                        <div className="flex items-center gap-2">
                            <Sparkles size={18} className="text-accent" />
                            <h3 className="text-base font-bold text-[var(--text-primary)]">{t('tryOn.resultTitle')}</h3>
                        </div>
                        <img
                            src={resultUrl}
                            alt={t('tryOn.resultTitle')}
                            className="media-tile w-full max-h-[60vh] object-contain p-2"
                        />
                        <div className="flex gap-2">
                            <button type="button" className="btn-secondary flex-1" onClick={onRetry}>
                                <RefreshCw size={16} />
                                {t('tryOn.regenerate')}
                            </button>
                            <button type="button" className="btn-primary flex-1" onClick={onClose}>
                                {t('tryOn.close')}
                            </button>
                        </div>
                    </>
                )}

                {phase === 'error' && (
                    <>
                        <h3 className="text-base font-bold text-[var(--text-primary)]">{t('tryOn.failedTitle')}</h3>
                        <p className="text-sm text-red-500 break-words">{errorMessage}</p>
                        <div className="flex gap-2">
                            <button type="button" className="btn-secondary flex-1" onClick={onClose}>
                                {t('tryOn.close')}
                            </button>
                            <button type="button" className="btn-primary flex-1" onClick={onRetry}>
                                <RefreshCw size={16} />
                                {t('tryOn.regenerate')}
                            </button>
                        </div>
                    </>
                )}
            </div>
        </div>
    )
}