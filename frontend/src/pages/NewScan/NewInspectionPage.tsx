import React, { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertCircle,
  ArrowRight,
  Layers,
  Loader2,
  Plus,
  ScanLine,
  UploadCloud,
  X,
} from 'lucide-react'
import Card from '../../components/common/Card'
import Button from '../../components/common/Button'
import { createScan, getScan } from '../../services/scanService'
import type { ApiErrorDetail } from '../../services/api'
import type { ScanResponse } from '../../types'

const SUPPORTED_CATEGORIES = [
  'Food Grains',
  'Edible Oil',
  'Packaged Food',
  'Snacks',
  'Beverages',
  'Dairy',
  'Cosmetics',
  'Pharmaceuticals',
  'General Commodity',
]

interface ViewItem {
  id: string
  file: File
  previewUrl: string
}

export const NewInspectionPage: React.FC = () => {
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const addFileInputRef = useRef<HTMLInputElement>(null)
  const isMountedRef = useRef<boolean>(true)
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const [views, setViews] = useState<ViewItem[]>([])
  const [productCategory, setProductCategory] = useState<string>('')
  const [isCompleteScan, setIsCompleteScan] = useState<boolean>(false)
  const [isDragging, setIsDragging] = useState<boolean>(false)

  // Scan Lifecycle State
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false)
  const [scanId, setScanId] = useState<string | null>(null)
  const [, setScanStatus] = useState<'idle' | 'uploading' | 'pending' | 'processing' | 'complete' | 'failed'>('idle')
  const [statusMessage, setStatusMessage] = useState<string>('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current)
      }
      views.forEach((v) => URL.revokeObjectURL(v.previewUrl))
    }
  }, [views])

  const validateAndAddFiles = (fileList: FileList | File[]) => {
    const validFiles: File[] = []
    let validationError: string | null = null

    for (let i = 0; i < fileList.length; i++) {
      const file = fileList[i]
      if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
        validationError = 'Unsupported file type. Please upload JPEG, PNG, or WebP images.'
        continue
      }
      if (file.size > 20 * 1024 * 1024) {
        validationError = 'File size exceeds 20MB limit.'
        continue
      }
      validFiles.push(file)
    }

    if (validationError && validFiles.length === 0) {
      setErrorMessage(validationError)
      return
    }

    if (validFiles.length > 0) {
      setErrorMessage(null)
      const newItems: ViewItem[] = validFiles.map((file) => ({
        id: `${file.name}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        file,
        previewUrl: URL.createObjectURL(file),
      }))
      setViews((prev) => [...prev, ...newItems])
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndAddFiles(e.dataTransfer.files)
    }
  }

  const removeView = (id: string) => {
    setViews((prev) => {
      const target = prev.find((v) => v.id === id)
      if (target) {
        URL.revokeObjectURL(target.previewUrl)
      }
      return prev.filter((v) => v.id !== id)
    })
  }

  const resetSelection = () => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current)
    }
    views.forEach((v) => URL.revokeObjectURL(v.previewUrl))
    setViews([])
    setIsSubmitting(false)
    setScanId(null)
    setScanStatus('idle')
    setStatusMessage('')
    setErrorMessage(null)
  }

  const pollScanStatus = (id: string, attempt: number = 0) => {
    const maxAttempts = 30 // 30 attempts * 1.5s = 45s max timeout
    const intervalMs = 1500

    if (!isMountedRef.current) return

    if (attempt >= maxAttempts) {
      setScanStatus('failed')
      setIsSubmitting(false)
      setErrorMessage('Inspection processing timed out. The server took longer than expected.')
      return
    }

    pollTimerRef.current = setTimeout(async () => {
      if (!isMountedRef.current) return

      try {
        const scanRes: ScanResponse = await getScan(id)
        if (!isMountedRef.current) return

        if (scanRes.status === 'complete') {
          setScanStatus('complete')
          setIsSubmitting(false)
          setStatusMessage('Inspection complete! Redirecting to results...')
          setTimeout(() => {
            if (isMountedRef.current) {
              navigate(`/inspection/${id}`)
            }
          }, 600)
        } else if (scanRes.status === 'failed') {
          setScanStatus('failed')
          setIsSubmitting(false)
          setErrorMessage('Package compliance inspection failed during processing.')
        } else {
          // Still pending or processing
          setScanStatus('processing')
          setStatusMessage(
            attempt > 8
              ? 'Fusing multi-view declarations and evaluating Legal Metrology rules...'
              : attempt > 3
              ? 'Extracting package declarations with OCR & Gemini AI...'
              : 'Preprocessing package views and executing quality audit...'
          )
          pollScanStatus(id, attempt + 1)
        }
      } catch (err) {
        if (!isMountedRef.current) return
        const apiErr = err as ApiErrorDetail
        setScanStatus('failed')
        setIsSubmitting(false)
        setErrorMessage(apiErr.message || 'Failed to poll scan status.')
      }
    }, intervalMs)
  }

  const handleSubmitScan = async () => {
    if (views.length === 0) {
      setErrorMessage('Please select or capture at least one package image.')
      return
    }

    try {
      setIsSubmitting(true)
      setErrorMessage(null)
      setScanStatus('uploading')
      setStatusMessage(
        views.length > 1
          ? `Uploading ${views.length} package views to PackSure server...`
          : 'Uploading package image to PackSure server...'
      )

      const files = views.map((v) => v.file)
      const initRes = await createScan({
        images: files,
        is_complete_scan: isCompleteScan,
        product_category: productCategory.trim() ? productCategory.trim() : undefined,
      })

      if (!isMountedRef.current) return

      setScanId(initRes.scan_id)
      setScanStatus('pending')
      setStatusMessage('Images accepted. Starting compliance pipeline...')

      // Begin safe polling loop
      pollScanStatus(initRes.scan_id, 0)
    } catch (err) {
      if (!isMountedRef.current) return
      const apiErr = err as ApiErrorDetail
      setIsSubmitting(false)
      setScanStatus('failed')
      setErrorMessage(apiErr.message || 'Failed to initiate package inspection.')
    }
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
          New Inspection
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Upload or capture single or multi-view package images for Legal Metrology (Packaged Commodities) Rules, 2011 compliance verification.
        </p>
      </div>

      {errorMessage && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3 text-sm text-red-800 animate-in fade-in">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <span className="font-semibold">Inspection Error:</span> {errorMessage}
          </div>
          <button
            onClick={() => setErrorMessage(null)}
            className="text-red-500 hover:text-red-700 p-0.5"
            aria-label="Dismiss error"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Upload Workstation */}
      <Card
        title="Package Upload Workstation"
        subtitle="Supported formats: JPEG, PNG, WebP (Max: 20MB per image)"
      >
        <div className="space-y-6">
          {/* File Dropzone Area */}
          {views.length === 0 ? (
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`flex flex-col items-center justify-center py-16 border-2 border-dashed rounded-lg transition-all cursor-pointer ${
                isDragging
                  ? 'border-brand-blue bg-blue-50/60 scale-[0.99]'
                  : 'border-slate-200 bg-slate-50/50 hover:bg-slate-50 hover:border-slate-300'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files && e.target.files.length > 0) {
                    validateAndAddFiles(e.target.files)
                  }
                }}
              />
              <div className="w-14 h-14 rounded-full bg-blue-50 text-brand-blue flex items-center justify-center mb-3 shadow-sm">
                <UploadCloud className="w-7 h-7" />
              </div>
              <h3 className="text-base font-semibold text-slate-800">
                Click to browse or drag and drop package image(s)
              </h3>
              <p className="text-xs text-slate-400 max-w-sm text-center mt-1">
                Upload single panel or multiple package views (Front, Back, Side) for comprehensive declaration fusion.
              </p>
              <div className="mt-4 flex items-center gap-2 text-xs text-slate-500 bg-white px-3 py-1.5 rounded-full border border-slate-200 shadow-2xs">
                <ScanLine className="w-3.5 h-3.5 text-brand-blue" />
                <span>Single-panel & multi-view evidence fusion supported</span>
              </div>
            </div>
          ) : (
            /* Multi-View / Selected File Thumbnail List */
            <div className="space-y-4">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <Layers className="w-4 h-4 text-brand-blue" />
                  <span className="text-sm font-bold text-slate-800">
                    Captured Package Views ({views.length})
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    ref={addFileInputRef}
                    type="file"
                    multiple
                    accept="image/jpeg,image/png,image/webp"
                    className="hidden"
                    onChange={(e) => {
                      if (e.target.files && e.target.files.length > 0) {
                        validateAndAddFiles(e.target.files)
                      }
                    }}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={isSubmitting}
                    icon={<Plus className="w-3.5 h-3.5" />}
                    onClick={() => addFileInputRef.current?.click()}
                  >
                    Add package view
                  </Button>
                </div>
              </div>

              {/* View Cards Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {views.map((item, idx) => (
                  <div
                    key={item.id}
                    className="p-3 bg-slate-50 border border-slate-200 rounded-lg flex items-center gap-3 relative group"
                  >
                    <img
                      src={item.previewUrl}
                      alt={`Package View ${idx + 1}`}
                      className="w-16 h-16 object-cover rounded-md border border-slate-300 shadow-2xs flex-shrink-0"
                    />
                    <div className="flex-1 min-w-0 pr-6">
                      <span className="inline-block text-[11px] font-bold text-brand-blue bg-blue-50 px-1.5 py-0.5 rounded mb-1">
                        View {idx + 1}
                      </span>
                      <p className="text-xs font-semibold text-slate-800 truncate" title={item.file.name}>
                        {item.file.name}
                      </p>
                      <p className="text-[10px] text-slate-400">
                        {(item.file.size / (1024 * 1024)).toFixed(2)} MB
                      </p>
                    </div>
                    {!isSubmitting && (
                      <button
                        onClick={() => removeView(item.id)}
                        className="absolute top-2 right-2 text-slate-400 hover:text-red-600 p-1 rounded transition-colors"
                        title="Remove view"
                        aria-label="Remove view"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                ))}
              </div>

              <div className="pt-1 flex items-center justify-between text-xs text-slate-500">
                <span>{views.length} package panel view{views.length > 1 ? 's' : ''} staged for inspection</span>
                <button
                  onClick={resetSelection}
                  disabled={isSubmitting}
                  className="text-red-600 hover:text-red-700 font-medium inline-flex items-center gap-1 disabled:opacity-50"
                >
                  <X className="w-3.5 h-3.5" /> Clear all views
                </button>
              </div>
            </div>
          )}

          {/* Inspection Options: Category & Complete-Scan Flag */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-slate-100">
            <div>
              <label htmlFor="product-category" className="block text-xs font-semibold text-slate-700 mb-1">
                Product Category Hint (Optional)
              </label>
              <select
                id="product-category"
                value={productCategory}
                onChange={(e) => setProductCategory(e.target.value)}
                disabled={isSubmitting}
                className="w-full text-sm rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-800 shadow-2xs focus:border-brand-blue focus:outline-none focus:ring-1 focus:ring-brand-blue disabled:bg-slate-100 disabled:text-slate-400"
              >
                <option value="">Auto-infer Category</option>
                {SUPPORTED_CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
              <p className="text-[11px] text-slate-400 mt-1">
                Helps apply category-specific exemptions and mandatory rules.
              </p>
            </div>

            <div className="flex flex-col justify-start">
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Inspection Completeness
              </label>
              <label className="flex items-start gap-2.5 p-2 rounded-lg border border-slate-200 bg-slate-50 hover:bg-slate-100/70 cursor-pointer transition-colors">
                <input
                  type="checkbox"
                  checked={isCompleteScan}
                  onChange={(e) => setIsCompleteScan(e.target.checked)}
                  disabled={isSubmitting}
                  className="mt-0.5 rounded border-slate-300 text-brand-blue focus:ring-brand-blue h-4 w-4"
                />
                <div className="text-xs">
                  <span className="font-semibold text-slate-800">Complete Package Scan</span>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Indicates all package panels have been captured. Enables strict statutory missing-declaration evaluation.
                  </p>
                </div>
              </label>
            </div>
          </div>

          {/* Processing Progress Status Display */}
          {isSubmitting && (
            <div className="p-4 bg-blue-50/80 border border-blue-200 rounded-lg space-y-3 animate-in fade-in">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm font-semibold text-blue-900">
                  <Loader2 className="w-4 h-4 animate-spin text-brand-blue" />
                  <span>{statusMessage || 'Processing package inspection...'}</span>
                </div>
                {scanId && (
                  <span className="text-[11px] font-mono text-blue-700 bg-blue-100 px-2 py-0.5 rounded">
                    ID: {scanId.slice(0, 8)}...
                  </span>
                )}
              </div>
              <div className="w-full bg-blue-200 rounded-full h-1.5 overflow-hidden">
                <div className="bg-brand-blue h-full w-full animate-pulse" />
              </div>
              <p className="text-xs text-blue-700/80">
                Running OpenCV quality check $\rightarrow$ Tesseract OCR $\rightarrow$ Gemini structured extraction $\rightarrow$ Multi-view evidence fusion $\rightarrow$ Rule engine audit.
              </p>
            </div>
          )}

          {/* Submission Action Bar */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
            {views.length > 0 && !isSubmitting && (
              <Button variant="outline" onClick={resetSelection}>
                Cancel
              </Button>
            )}
            <Button
              onClick={handleSubmitScan}
              disabled={views.length === 0 || isSubmitting}
              icon={
                isSubmitting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <ArrowRight className="w-4 h-4" />
                )
              }
            >
              {isSubmitting
                ? 'Analyzing Package...'
                : views.length > 1
                ? `Run Multi-View Compliance Scan (${views.length} views)`
                : 'Run Compliance Scan'}
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}

export default NewInspectionPage
