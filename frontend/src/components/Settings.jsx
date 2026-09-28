import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useTheme } from '../contexts/ThemeContext'
import { Sun, Moon, Globe, Sparkles, MapPin, X, ChevronDown, List, Cable } from 'lucide-react'
import { API_BASE } from '../utils/api'

const LANGUAGES = [
    { code: 'zh', label: '中文' },
    { code: 'en', label: 'English' },
    { code: 'ja', label: '日本語' }
]

const ZODIAC_SIGNS = [
    'aries',
    'taurus',
    'gemini',
    'cancer',
    'leo',
    'virgo',
    'libra',
    'scorpio',
    'sagittarius',
    'capricorn',
    'aquarius',
    'pisces'
]

const DEFAULT_LOCATION = '上海, 上海市, 中国'
const DEFAULT_REFRESH_CONFIG = {
    weather_location: DEFAULT_LOCATION,
    zodiac_sign: ''
}
const LOCATION_ID_REGEX = /^\d{9}$/
const COORDINATE_LOCATION_REGEX = /^\s*-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?\s*$/
const LOCATION_PART_SEPARATOR_REGEX = /[，,]+/
const LOCATION_PRESETS = [
    '上海, 上海市, 中国',
    '北京, 北京市, 中国',
    '南京, 江苏, 中国',
    '杭州, 浙江, 中国',
    '广州, 广东, 中国',
    '深圳, 广东, 中国'
]

const getRefreshConfig = (config) => ({
    weather_location: (config.weather_location || '').trim() || DEFAULT_LOCATION,
    zodiac_sign: config.zodiac_sign || ''
})

const formatLocationCandidate = (city) => {
    const name = (city?.name || '').trim()
    const state = (city?.adm1 || city?.adm2 || '').trim()
    const country = (city?.country || '').trim()
    if (!name || !state || !country) return null

    const value = `${name}, ${state}, ${country}`
    const labelParts = [city.name]
    if (city.adm2 && city.adm2 !== city.name) labelParts.push(city.adm2)
    if (city.adm1 && city.adm1 !== city.adm2 && city.adm1 !== city.name) labelParts.push(city.adm1)
    if (city.country) labelParts.push(city.country)

    return {
        value,
        label: labelParts.filter(Boolean).join(' · ')
    }
}

const isCompleteLocationInput = (location) => {
    const raw = (location || '').trim()
    if (!raw) return false
    if (LOCATION_ID_REGEX.test(raw) || COORDINATE_LOCATION_REGEX.test(raw)) return true

    const parts = raw
        .split(LOCATION_PART_SEPARATOR_REGEX)
        .map(part => part.trim())
        .filter(Boolean)

    return parts.length >= 3
}

const Settings = ({ isOpen, onClose, onSave }) => {
    const { t, i18n } = useTranslation()
    const { theme, toggleTheme } = useTheme()
    const [config, setConfig] = useState({
        api_base: 'https://api.openai.com/v1',
        api_key: '',
        model: 'gpt-4o',
        removebg_api_key: '',
        bg_removal_method: 'local',
        tryon_provider: 'disabled',
        tryon_api_url: '',
        tryon_api_key: '',
        tryon_model: '',
        weather_location: DEFAULT_LOCATION,
        zodiac_sign: '',
        experimental_garment_pipeline: false,
        vision_model: 'qwen3.8-flash',
        image_model: 'qwen-image-3.0-pro',
        image_api_base: '',
        image_api_key: '',
        image_reference_transport: 'base64'
    })
    const [models, setModels] = useState([])
    const [loading, setLoading] = useState(false)
    const [testing, setTesting] = useState(false)
    const [testResult, setTestResult] = useState(null)
    const [hasExistingKey, setHasExistingKey] = useState(false)
    const [hasRemoveBgKey, setHasRemoveBgKey] = useState(false)
    const [hasTryonApiKey, setHasTryonApiKey] = useState(false)
    const [hasImageApiKey, setHasImageApiKey] = useState(false)
    const [showModelSelect, setShowModelSelect] = useState(false)
    const [locationSuggestions, setLocationSuggestions] = useState([])
    const [searchingLocations, setSearchingLocations] = useState(false)
    const [showLocationDropdown, setShowLocationDropdown] = useState(false)
    const [installingRembg, setInstallingRembg] = useState(false)
    const [localRembgInstalled, setLocalRembgInstalled] = useState(false)
    const [initialRefreshConfig, setInitialRefreshConfig] = useState(DEFAULT_REFRESH_CONFIG)
    const locationPickerRef = useRef(null)

    useEffect(() => {
        if (isOpen) {
            const controller = new AbortController()
            void fetchConfig(controller.signal)
            document.body.style.overflow = 'hidden'
            return () => {
                controller.abort()
                document.body.style.overflow = ''
            }
        }

        document.body.style.overflow = ''
        return () => {
            document.body.style.overflow = ''
        }
    }, [isOpen])

    useEffect(() => {
        if (!showLocationDropdown) {
            return
        }

        const handleOutsidePointerDown = (event) => {
            if (locationPickerRef.current && !locationPickerRef.current.contains(event.target)) {
                setShowLocationDropdown(false)
            }
        }

        document.addEventListener('mousedown', handleOutsidePointerDown)
        return () => {
            document.removeEventListener('mousedown', handleOutsidePointerDown)
        }
    }, [showLocationDropdown])

    useEffect(() => {
        if (!showLocationDropdown) {
            return
        }

        const query = (config.weather_location || '').trim()
        const filteredPresets = LOCATION_PRESETS
            .filter(location => !query || location.toLowerCase().includes(query.toLowerCase()))
            .map(location => ({ value: location, label: location }))

        const controller = new AbortController()
        const timer = setTimeout(async () => {
            if (!query) {
                setLocationSuggestions(filteredPresets)
                setSearchingLocations(false)
                return
            }

            setSearchingLocations(true)
            try {
                const response = await fetch(`${API_BASE}/cities?query=${encodeURIComponent(query)}&limit=10`, {
                    signal: controller.signal
                })
                if (!response.ok) {
                    setLocationSuggestions(filteredPresets)
                    return
                }
                const cities = await response.json()
                const cityOptions = (cities || [])
                    .map(formatLocationCandidate)
                    .filter(Boolean)

                const deduped = []
                const seen = new Set()
                for (const item of [...filteredPresets, ...cityOptions]) {
                    if (seen.has(item.value)) continue
                    seen.add(item.value)
                    deduped.push(item)
                }
                setLocationSuggestions(deduped)
            } catch (error) {
                if (error.name !== 'AbortError') {
                    console.error('Failed to search city suggestions:', error)
                    setLocationSuggestions(filteredPresets)
                }
            } finally {
                if (!controller.signal.aborted) {
                    setSearchingLocations(false)
                }
            }
        }, 250)

        return () => {
            controller.abort()
            clearTimeout(timer)
        }
    }, [config.weather_location, showLocationDropdown])

    const fetchConfig = async (signal) => {
        try {
            const response = await fetch(`${API_BASE}/config`, { signal })
            if (response.ok) {
                const data = await response.json()
                const refreshConfig = getRefreshConfig(data)
                setConfig(prev => ({
                    ...prev,
                    api_base: data.api_base || 'https://api.openai.com/v1',
                    model: data.model || 'gpt-4o',
                    bg_removal_method: data.bg_removal_method || 'local',
                    tryon_provider: data.tryon_provider || 'disabled',
                    tryon_api_url: data.tryon_api_url || '',
                    tryon_model: data.tryon_model || '',
                    weather_location: refreshConfig.weather_location,
                    zodiac_sign: refreshConfig.zodiac_sign,
                    experimental_garment_pipeline: Boolean(data.experimental_garment_pipeline),
                    vision_model: data.vision_model || 'qwen3.8-flash',
                    image_model: data.image_model || 'qwen-image-3.0-pro',
                    image_api_base: data.image_api_base || '',
                    image_reference_transport: data.image_reference_transport || 'base64'
                }))
                setInitialRefreshConfig(refreshConfig)
                setHasExistingKey(data.has_api_key)
                setHasRemoveBgKey(data.has_removebg_key)
                setHasTryonApiKey(data.has_tryon_api_key)
                setHasImageApiKey(data.has_image_api_key)
                setLocalRembgInstalled(Boolean(data.local_rembg_installed))
            }
        } catch (error) {
            if (error.name !== 'AbortError') {
                console.error('Failed to fetch config:', error)
            }
        }
    }

    const fetchModels = async () => {
        setLoading(true)
        try {
            const response = await fetch(`${API_BASE}/models`)
            if (response.ok) {
                const data = await response.json()
                setModels(data.models || [])
                if (data.models && data.models.length > 0) {
                    setShowModelSelect(true)
                }
            }
        } catch (error) {
            console.error('Failed to fetch models:', error)
        } finally {
            setLoading(false)
        }
    }

    const handleTestConnection = async () => {
        setTesting(true)
        setTestResult(null)

        const saveSuccess = await handleSave(false)
        if (!saveSuccess) {
            setTesting(false)
            return
        }

        try {
            const response = await fetch(`${API_BASE}/test-connection`, {
                method: 'POST'
            })
            const data = await response.json()
            setTestResult(data)

            if (data.success) {
                fetchModels()
            }
        } catch {
            setTestResult({
                success: false,
                message: t('settings.testFailed')
            })
        } finally {
            setTesting(false)
        }
    }

    const handleInstallRembg = async () => {
        setInstallingRembg(true)
        try {
            const response = await fetch(`${API_BASE}/install-rembg`, {
                method: 'POST'
            })
            const data = await response.json().catch(() => ({}))
            if (data.success) {
                setLocalRembgInstalled(Boolean(data.local_rembg_installed ?? true))
            }
            setTestResult({
                success: Boolean(data.success),
                message: data.message || (data.success ? t('settings.installRembgSuccess') : t('settings.installRembgFailed'))
            })
        } catch {
            setTestResult({
                success: false,
                message: t('settings.installRembgFailed')
            })
        } finally {
            setInstallingRembg(false)
        }
    }

    const handleSave = async (closeAfter = true) => {
        try {
            const normalizedLocation = (config.weather_location || '').trim() || DEFAULT_LOCATION
            if (!isCompleteLocationInput(normalizedLocation)) {
                setTestResult({
                    success: false,
                    message: t('settings.defaultCityFormatError')
                })
                return false
            }

            const payload = {
                api_base: config.api_base,
                model: config.model,
                bg_removal_method: config.bg_removal_method,
                tryon_provider: config.tryon_provider,
                tryon_api_url: config.tryon_api_url,
                tryon_model: config.tryon_model,
                weather_location: normalizedLocation,
                zodiac_sign: config.zodiac_sign,
                experimental_garment_pipeline: config.experimental_garment_pipeline,
                vision_model: config.vision_model,
                image_model: config.image_model,
                image_api_base: config.image_api_base,
                image_reference_transport: config.image_reference_transport
            }

            if (config.api_key) {
                payload.api_key = config.api_key
            }
            if (config.removebg_api_key) {
                payload.removebg_api_key = config.removebg_api_key
            }
            if (config.tryon_api_key) {
                payload.tryon_api_key = config.tryon_api_key
            }
            if (config.image_api_key) {
                payload.image_api_key = config.image_api_key
            }

            const response = await fetch(`${API_BASE}/config`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            })

            if (response.ok) {
                const nextRefreshConfig = {
                    weather_location: normalizedLocation,
                    zodiac_sign: config.zodiac_sign || ''
                }
                const refreshChanges = {
                    ...nextRefreshConfig,
                    weatherLocationChanged: nextRefreshConfig.weather_location !== initialRefreshConfig.weather_location,
                    zodiacSignChanged: nextRefreshConfig.zodiac_sign !== initialRefreshConfig.zodiac_sign
                }

                if (closeAfter) {
                    setInitialRefreshConfig(nextRefreshConfig)
                    onSave && onSave(refreshChanges)
                    onClose()
                }
                return true
            }
            const errorPayload = await response.json().catch(() => ({}))
            setTestResult({
                success: false,
                message: errorPayload.detail || t('settings.defaultCityFormatError')
            })
            return false
        } catch (error) {
            console.error('Failed to save config:', error)
            return false
        }
    }

    const changeLanguage = (lng) => {
        i18n.changeLanguage(lng)
    }

    if (!isOpen) return null

    return (
        <div className="fixed inset-0 z-[100] flex items-end sm:items-center justify-center bg-black/35 backdrop-blur-md transition-opacity" onClick={onClose}>
            <div
                className="liquid-sheet w-full max-w-lg rounded-t-[30px] sm:rounded-[30px] max-h-[90vh] sm:max-h-[85vh] flex flex-col animate-[slideUp_0.3s_ease-out] overflow-hidden"
                onClick={e => e.stopPropagation()}
            >
                <div className="flex items-center justify-between p-5 border-b border-[var(--line)] px-6">
                    <h2 className="text-xl font-bold text-[var(--text-primary)] tracking-tight">{t('settings.title')}</h2>
                    <button className="btn-icon !min-h-9 !min-w-9 !p-0" onClick={onClose} aria-label={t('settings.cancel')}>
                        <X size={18} />
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto p-6 space-y-8">
                    {/* App Settings Section */}
                    <div className="space-y-4">
                        <div className="text-xs font-bold tracking-widest text-zinc-400 uppercase">{t('settings.appSection')}</div>

                        {/* Language Switcher */}
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 flex items-center gap-1.5">
                                <Globe size={16} className="text-accent" />
                                {t('settings.language')}
                            </label>
                            <div className="flex gap-2">
                                {LANGUAGES.map(lang => (
                                    <button
                                        key={lang.code}
                                        className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-all duration-200 ${
                                            i18n.language === lang.code || (i18n.language.startsWith(lang.code))
                                                ? 'bg-accent text-white shadow-sm'
                                                : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-700'
                                        }`}
                                        onClick={() => changeLanguage(lang.code)}
                                    >
                                        {lang.label}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Theme Switcher */}
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 flex items-center gap-1.5">
                                {theme === 'dark' ? <Moon size={16} className="text-accent" /> : <Sun size={16} className="text-accent" />}
                                {t('settings.theme')}
                            </label>
                            <div className="flex gap-2">
                                <button
                                    className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-all duration-200 flex items-center justify-center gap-2 ${
                                        theme === 'light'
                                            ? 'bg-accent text-white shadow-sm'
                                            : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-700'
                                    }`}
                                    onClick={() => theme !== 'light' && toggleTheme()}
                                >
                                    <Sun size={14} />
                                    {t('settings.themeLight')}
                                </button>
                                <button
                                    className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-all duration-200 flex items-center justify-center gap-2 ${
                                        theme === 'dark'
                                            ? 'bg-accent text-white shadow-sm'
                                            : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-700'
                                    }`}
                                    onClick={() => theme !== 'dark' && toggleTheme()}
                                >
                                    <Moon size={14} />
                                    {t('settings.themeDark')}
                                </button>
                            </div>
                        </div>

                        <div className="space-y-2">
                            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 flex items-center gap-1.5">
                                <Sparkles size={16} className="text-accent" />
                                {t('settings.zodiac')}
                            </label>
                            <select
                                className="input-field appearance-none"
                                value={config.zodiac_sign}
                                onChange={e => setConfig(prev => ({ ...prev, zodiac_sign: e.target.value }))}
                            >
                                <option value="">{t('settings.zodiacPlaceholder')}</option>
                                {ZODIAC_SIGNS.map(sign => (
                                    <option key={sign} value={sign}>
                                        {t(`settings.zodiacOptions.${sign}`)}
                                    </option>
                                ))}
                            </select>
                        </div>

                        <div className="space-y-2">
                            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 flex items-center gap-1.5">
                                <MapPin size={16} className="text-accent" />
                                {t('settings.defaultCity')}
                            </label>
                            <div className="relative" ref={locationPickerRef}>
                                <input
                                    type="text"
                                    className="input-field pr-10"
                                    value={config.weather_location}
                                    onFocus={() => setShowLocationDropdown(true)}
                                    onChange={e => {
                                        setConfig(prev => ({ ...prev, weather_location: e.target.value }))
                                        setShowLocationDropdown(true)
                                        if (testResult?.success === false) {
                                            setTestResult(null)
                                        }
                                    }}
                                    placeholder={t('settings.defaultCityPlaceholder')}
                                />
                                <button
                                    type="button"
                                    className="btn-icon absolute right-2 top-1/2 -translate-y-1/2 !h-7 !min-h-7 !w-7 !min-w-7 !p-0"
                                    onClick={() => setShowLocationDropdown(open => !open)}
                                    aria-label={t('settings.defaultCity')}
                                >
                                    <ChevronDown size={15} />
                                </button>

                                {showLocationDropdown && (
                                    <div className="liquid-panel absolute z-40 mt-1 w-full max-h-56 overflow-y-auto rounded-2xl">
                                        {locationSuggestions.length > 0 ? (
                                            locationSuggestions.map(option => (
                                                <button
                                                    key={option.value}
                                                    type="button"
                                                    className="w-full text-left px-3 py-2.5 text-sm text-zinc-800 dark:text-zinc-200 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors"
                                                    onMouseDown={(event) => {
                                                        event.preventDefault()
                                                        setConfig(prev => ({ ...prev, weather_location: option.value }))
                                                        setShowLocationDropdown(false)
                                                        if (testResult?.success === false) {
                                                            setTestResult(null)
                                                        }
                                                    }}
                                                >
                                                    {option.label}
                                                </button>
                                            ))
                                        ) : searchingLocations ? (
                                            <div className="px-3 py-2.5 text-sm text-zinc-500">{t('recommendation.searching')}</div>
                                        ) : (
                                            <div className="px-3 py-2.5 text-sm text-zinc-500">{t('recommendation.noCity')}</div>
                                        )}
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

                    <div className="h-px bg-zinc-200/60 dark:bg-zinc-700/60 w-full" />

                    {/* LLM Section */}
                    <div className="space-y-4">
                        <div className="text-xs font-bold tracking-widest text-zinc-400 uppercase">{t('settings.llmSection')}</div>

                        <div className="space-y-2">
                            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 flex justify-between">
                                {t('settings.apiBaseLabel')}
                                <span className="text-zinc-400 font-normal">{t('settings.apiBaseHint')}</span>
                            </label>
                            <input
                                type="url"
                                className="input-field"
                                value={config.api_base}
                                onChange={e => setConfig(prev => ({ ...prev, api_base: e.target.value }))}
                                placeholder="https://api.openai.com/v1"
                            />
                        </div>

                        <div className="space-y-2">
                            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 flex justify-between">
                                {t('settings.apiKeyLabel')}
                                {hasExistingKey && !config.api_key && (
                                    <span className="text-green-500 font-normal text-xs bg-green-50 dark:bg-green-900/30 px-2 py-0.5 rounded">{t('settings.configured')}</span>
                                )}
                            </label>
                            <input
                                type="password"
                                className="input-field font-mono"
                                value={config.api_key}
                                onChange={e => setConfig(prev => ({ ...prev, api_key: e.target.value }))}
                                placeholder={hasExistingKey ? `••••••••（${t('settings.keepEmpty')}）` : "sk-..."}
                            />
                        </div>

                        <div className="space-y-2 relative">
                            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 flex justify-between">
                                {t('settings.model')}
                                {loading && <span className="text-zinc-400 font-normal animate-pulse text-xs">{t('settings.fetching')}</span>}
                            </label>
                            <div className="flex gap-2 relative">
                                {models.length > 0 && showModelSelect ? (
                                    <div className="relative flex-1">
                                        <select
                                            className="input-field appearance-none"
                                            value={config.model}
                                            onChange={e => {
                                                if (e.target.value === '__custom__') {
                                                    setShowModelSelect(false)
                                                } else {
                                                    setConfig(prev => ({ ...prev, model: e.target.value }))
                                                }
                                            }}
                                        >
                                            {!models.find(m => m.id === config.model) && config.model && (
                                                <option value={config.model}>{config.model}</option>
                                            )}
                                            {models.map(m => (
                                                <option key={m.id} value={m.id}>{m.name}</option>
                                            ))}
                                            <option value="__custom__">{t('settings.manualInput')}</option>
                                        </select>
                                    </div>
                                ) : (
                                    <div className="flex-1 relative group">
                                        <input
                                            type="text"
                                            className="input-field"
                                            value={config.model}
                                            onChange={e => setConfig(prev => ({ ...prev, model: e.target.value }))}
                                            placeholder="gpt-4o"
                                            list="model-list"
                                        />
                                        {models.length > 0 && (
                                            <button
                                                className="btn-icon absolute right-2 top-1/2 -translate-y-1/2 !h-8 !min-h-8 !w-8 !min-w-8 !p-0"
                                                onClick={() => setShowModelSelect(true)}
                                                title={t('settings.switchToList')}
                                            >
                                                <List size={15} />
                                            </button>
                                        )}
                                    </div>
                                )}
                                <button className="btn-secondary px-3 shrink-0" onClick={fetchModels} disabled={loading}>
                                    {t('settings.fetch')}
                                </button>
                            </div>
                        </div>

                        <div className="pt-2">
                            <button
                                className={`w-full py-2.5 rounded-lg border flex items-center justify-center gap-2 font-medium transition-colors ${
                                    testResult?.success ? 'border-green-200 bg-green-50 dark:bg-green-900/30 dark:border-green-800 text-green-700 dark:text-green-400' :
                                    testResult?.success === false ? 'border-red-200 bg-red-50 dark:bg-red-900/30 dark:border-red-800 text-red-700 dark:text-red-400' :
                                    'border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-700 hover:border-zinc-300'
                                }`}
                                onClick={handleTestConnection}
                                disabled={testing}
                            >
                                {testing ? <span className="w-4 h-4 border-2 border-zinc-400 border-t-zinc-600 rounded-full animate-spin"></span> : <Cable size={16} />}
                                {testing ? t('settings.testing') : testResult ? testResult.message : t('settings.testConnection')}
                            </button>
                        </div>

                        <div className="pt-2">
                            <p className="text-xs text-zinc-500 mb-2 font-medium">{t('settings.presets')}</p>
                            <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
                                {[
                                    { name: 'OpenAI', base: 'https://api.openai.com/v1', model: 'gpt-4o' },
                                    { name: 'Anthropic', base: 'https://api.anthropic.com/v1', model: 'claude-3-5-sonnet-latest' },
                                    { name: 'Google', base: 'https://generativelanguage.googleapis.com/v1beta/openai', model: 'gemini-2.0-flash-exp' },
                                    { name: 'DeepSeek', base: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
                                ].map(p => (
                                    <button
                                        key={p.name}
                                        className="py-1.5 px-2 bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-md text-xs font-medium text-zinc-600 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-700 hover:text-zinc-900 dark:hover:text-zinc-200 transition-colors"
                                        onClick={() => setConfig(prev => ({ ...prev, api_base: p.base, model: p.model }))}
                                    >
                                        {p.name}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="pt-2 space-y-3">
                            <div className="text-xs font-bold tracking-widest text-zinc-400 uppercase">{t('settings.tryOnSection')}</div>

                            <div className="space-y-2">
                                <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{t('settings.tryOnProvider')}</label>
                                <select
                                    className="input-field appearance-none"
                                    value={config.tryon_provider}
                                    onChange={e => setConfig(prev => ({ ...prev, tryon_provider: e.target.value }))}
                                >
                                    <option value="disabled">{t('settings.tryOnDisabled')}</option>
                                    <option value="custom">{t('settings.tryOnCustom')}</option>
                                </select>
                            </div>

                            {config.tryon_provider === 'custom' && (
                                <>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{t('settings.tryOnApiUrl')}</label>
                                        <input
                                            type="url"
                                            className="input-field"
                                            value={config.tryon_api_url}
                                            onChange={e => setConfig(prev => ({ ...prev, tryon_api_url: e.target.value }))}
                                            placeholder={t('settings.tryOnApiUrlPlaceholder')}
                                        />
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 flex justify-between">
                                            {t('settings.tryOnApiKey')}
                                            {hasTryonApiKey && !config.tryon_api_key && (
                                                <span className="text-green-500 font-normal text-xs bg-green-50 dark:bg-green-900/30 px-2 py-0.5 rounded">{t('settings.configured')}</span>
                                            )}
                                        </label>
                                        <input
                                            type="password"
                                            className="input-field font-mono"
                                            value={config.tryon_api_key}
                                            onChange={e => setConfig(prev => ({ ...prev, tryon_api_key: e.target.value }))}
                                            placeholder={hasTryonApiKey ? `••••••••（${t('settings.keepEmpty')}）` : 'Bearer token'}
                                        />
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{t('settings.tryOnModel')}</label>
                                        <input
                                            type="text"
                                            className="input-field"
                                            value={config.tryon_model}
                                            onChange={e => setConfig(prev => ({ ...prev, tryon_model: e.target.value }))}
                                            placeholder={t('settings.tryOnModelPlaceholder')}
                                        />
                                    </div>
                                </>
                            )}
                        </div>

                        <div className="pt-2 space-y-3">
                            <div className="text-xs font-bold tracking-widest text-zinc-400 uppercase">{t('settings.captureSection')}</div>

                            <label className={`flex items-center justify-between gap-3 p-3 rounded-xl border-2 transition-colors cursor-pointer ${config.experimental_garment_pipeline ? 'border-accent bg-blue-50/20 dark:bg-blue-950/20' : 'border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900'}`}>
                                <div className="flex flex-col">
                                    <span className="font-medium text-zinc-900 dark:text-zinc-100 text-sm">{t('settings.captureEnabled')}</span>
                                    <span className="text-xs text-zinc-500 mt-0.5">{t('settings.captureEnabledDesc')}</span>
                                </div>
                                <input
                                    type="checkbox"
                                    className="w-5 h-5 shrink-0"
                                    checked={config.experimental_garment_pipeline}
                                    onChange={e => setConfig(prev => ({ ...prev, experimental_garment_pipeline: e.target.checked }))}
                                />
                            </label>

                            {config.experimental_garment_pipeline && (
                                <>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{t('settings.visionModel')}</label>
                                        <select
                                            className="input-field appearance-none"
                                            value={config.vision_model}
                                            onChange={e => setConfig(prev => ({ ...prev, vision_model: e.target.value }))}
                                        >
                                            {models.length > 0 ? (
                                                models.map(model => <option key={model.id} value={model.id}>{model.id}</option>)
                                            ) : (
                                                <option value={config.vision_model}>{config.vision_model}</option>
                                            )}
                                        </select>
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{t('settings.imageModel')}</label>
                                        <select
                                            className="input-field appearance-none"
                                            value={config.image_model}
                                            onChange={e => setConfig(prev => ({ ...prev, image_model: e.target.value }))}
                                        >
                                            {(() => {
                                                const imageModels = models.filter(model => /image|seedream/i.test(model.id))
                                                const options = imageModels.length > 0
                                                    ? imageModels
                                                    : [{ id: config.image_model, name: config.image_model }]
                                                return options.map(model => <option key={model.id} value={model.id}>{model.id}</option>)
                                            })()}
                                        </select>
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{t('settings.imageApiBase')}</label>
                                        <input
                                            type="text"
                                            className="input-field font-mono"
                                            value={config.image_api_base}
                                            onChange={e => setConfig(prev => ({ ...prev, image_api_base: e.target.value }))}
                                            placeholder={config.api_base || 'https://api.example.com/v1'}
                                        />
                                        <p className="text-xs text-zinc-500">{t('settings.imageApiBaseHint')}</p>
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 flex justify-between">
                                            {t('settings.imageApiKey')}
                                            {hasImageApiKey && !config.image_api_key && (
                                                <span className="text-green-500 font-normal text-xs bg-green-50 dark:bg-green-900/30 px-2 py-0.5 rounded">{t('settings.configured')}</span>
                                            )}
                                        </label>
                                        <input
                                            type="password"
                                            className="input-field font-mono"
                                            value={config.image_api_key}
                                            onChange={e => setConfig(prev => ({ ...prev, image_api_key: e.target.value }))}
                                            placeholder={hasImageApiKey ? `••••••••（${t('settings.keepEmpty')}）` : t('settings.imageApiKeyPlaceholder')}
                                        />
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{t('settings.imageTransport')}</label>
                                        <select
                                            className="input-field appearance-none"
                                            value={config.image_reference_transport}
                                            onChange={e => setConfig(prev => ({ ...prev, image_reference_transport: e.target.value }))}
                                        >
                                            <option value="base64">{t('settings.imageTransportBase64')}</option>
                                            <option value="url">{t('settings.imageTransportUrl')}</option>
                                        </select>
                                    </div>

                                    <div className="pt-1">
                                        <p className="text-xs text-zinc-500 mb-2 font-medium">{t('settings.capturePresets')}</p>
                                        <div className="grid grid-cols-2 gap-2">
                                            <button
                                                type="button"
                                                className="py-1.5 px-2 bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-md text-xs font-medium text-zinc-600 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-700 transition-colors"
                                                onClick={() => setConfig(prev => ({ ...prev, vision_model: 'qwen3.8-flash', image_model: 'qwen-image-3.0-pro', image_api_base: '' }))}
                                            >
                                                {t('settings.presetQwen')}
                                            </button>
                                            <button
                                                type="button"
                                                className="py-1.5 px-2 bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-md text-xs font-medium text-zinc-600 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-700 transition-colors"
                                                onClick={() => setConfig(prev => ({ ...prev, image_model: 'doubao-seedream-5.0-lite', image_api_base: '' }))}
                                            >
                                                {t('settings.presetDoubao')}
                                            </button>
                                        </div>
                                    </div>
                                </>
                            )}
                        </div>
                    </div>

                    <div className="h-px bg-zinc-200/60 dark:bg-zinc-700/60 w-full" />

                    {/* Image Processing Section */}
                    <div className="space-y-4">
                        <div className="text-xs font-bold tracking-widest text-zinc-400 uppercase">{t('settings.imageSection')}</div>

                        <div className="flex flex-col gap-3">
                            <label className={`flex gap-3 p-3 rounded-xl border-2 transition-colors cursor-pointer ${config.bg_removal_method === 'local' ? 'border-accent bg-blue-50/20 dark:bg-blue-950/20' : 'border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 hover:border-zinc-300 dark:hover:border-zinc-600'}`}>
                                <input
                                    type="radio"
                                    name="bg_removal_method"
                                    value="local"
                                    className="mt-1"
                                    checked={config.bg_removal_method === 'local'}
                                    onChange={e => setConfig(prev => ({ ...prev, bg_removal_method: e.target.value }))}
                                />
                                <div className="flex flex-col">
                                    <span className="font-medium text-zinc-900 dark:text-zinc-100 text-sm">{t('settings.localRembg')}</span>
                                    <span className="text-xs text-zinc-500 mt-0.5">{t('settings.localRembgDesc')}</span>
                                    <span className="text-[11px] text-zinc-500 mt-1">{t('settings.localRembgOptional')}</span>
                                    <div className="mt-2 flex items-center gap-2">
                                        <button
                                            type="button"
                                            className="btn-secondary !py-1.5 !px-2 text-xs"
                                            onClick={handleInstallRembg}
                                            disabled={installingRembg || localRembgInstalled}
                                        >
                                            {localRembgInstalled
                                                ? t('settings.rembgInstalled')
                                                : installingRembg
                                                    ? t('settings.installingRembg')
                                                    : t('settings.installRembg')}
                                        </button>
                                        <code className="inline-block rounded bg-zinc-100 dark:bg-zinc-800 px-2 py-0.5 text-[11px] text-zinc-700 dark:text-zinc-200">{t('settings.localRembgInstall')}</code>
                                    </div>
                                </div>
                            </label>

                            <label className={`flex gap-3 p-3 rounded-xl border-2 transition-colors cursor-pointer ${config.bg_removal_method === 'removebg' ? 'border-accent bg-blue-50/20 dark:bg-blue-950/20' : 'border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 hover:border-zinc-300 dark:hover:border-zinc-600'}`}>
                                <input
                                    type="radio"
                                    name="bg_removal_method"
                                    value="removebg"
                                    className="mt-1"
                                    checked={config.bg_removal_method === 'removebg'}
                                    onChange={e => setConfig(prev => ({ ...prev, bg_removal_method: e.target.value }))}
                                />
                                <div className="flex flex-col">
                                    <span className="font-medium text-zinc-900 dark:text-zinc-100 text-sm flex items-center gap-2">
                                        remove.bg API
                                        <span className="px-1.5 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-500 text-[10px] font-bold">PRO</span>
                                    </span>
                                    <span className="text-xs text-zinc-500 mt-0.5">{t('settings.removebgDesc')}</span>
                                </div>
                            </label>
                        </div>

                        {config.bg_removal_method === 'removebg' && (
                            <div className="animate-fade-in space-y-2 mt-4">
                                <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 flex justify-between">
                                    remove.bg API Key
                                    {hasRemoveBgKey && !config.removebg_api_key && (
                                        <span className="text-green-500 font-normal text-xs bg-green-50 dark:bg-green-900/30 px-2 py-0.5 rounded">{t('settings.configured')}</span>
                                    )}
                                </label>
                                <input
                                    type="password"
                                    className="input-field font-mono"
                                    value={config.removebg_api_key}
                                    onChange={e => setConfig(prev => ({ ...prev, removebg_api_key: e.target.value }))}
                                    placeholder={hasRemoveBgKey ? `••••••••（${t('settings.keepEmpty')}）` : t('settings.removebgKeyPlaceholder')}
                                />
                                <div className="text-xs flex justify-end">
                                    <a href="https://www.remove.bg/api" target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">
                                        {t('settings.getKey')}
                                    </a>
                                </div>
                            </div>
                        )}
                    </div>

                    <div className="pb-4" />
                </div>

                <div className="p-5 border-t border-[var(--line)] flex gap-3 pb-safe">
                    <button className="btn-secondary flex-1" onClick={onClose}>
                        {t('settings.cancel')}
                    </button>
                    <button className="btn-primary flex-[2]" onClick={() => handleSave(true)}>
                        {t('settings.saveSettings')}
                    </button>
                </div>
            </div>

            <style>{`
                @keyframes slideUp {
                    from { transform: translateY(100%); opacity: 0; }
                    to { transform: translateY(0); opacity: 1; }
                }
            `}</style>
        </div>
    )
}

export default Settings
