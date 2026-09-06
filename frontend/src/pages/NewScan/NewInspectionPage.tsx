import React, { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertCircle,
  ArrowRight,
  FileImage,
  Loader2,
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

export const NewInspectionPage: React.FC = () => {
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const isMountedRef = useRef<boolean>(true)
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [productCategory, setProductCategory] = useState<string>('')
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
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl)
      }
    }
  }, [previewUrl])

  const handleFileChange = (file: File | null) => {
    if (!file) return
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      setErrorMessage('Unsupported file type. Please upload a JPEG, PNG, or WebP image.')
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      setErrorMessage('File size exceeds 10MB limit.')
      return
    }

    setErrorMessage(null)
    setSelectedFile(file)
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl)
    }
    setPreviewUrl(URL.createObjectURL(file))
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
      handleFileChange(e.dataTransfer.files[0])
    }
  }

  const resetSelection = () => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current)
    }
    setSelectedFile(null)
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl)
      setPreviewUrl(null)
    }
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
              ? 'Evaluating Legal Metrology rules and generating evidence overlay...'
              : attempt > 3
              ? 'Extracting mandatory declarations with Gemini AI...'
              : 'Preprocessing image and running OCR token extraction...'
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
    if (!selectedFile) {
      setErrorMessage('Please select or capture a package image first.')
      return
    }

    try {
      setIsSubmitting(true)
      setErrorMessage(null)
      setScanStatus('uploading')
      setStatusMessage('Uploading package image to PackSure server...')

      const initRes = await createScan({
        image: selectedFile,
        product_category: productCategory.trim() ? productCategory.trim() : undefined,
      })

      if (!isMountedRef.current) return

      setScanId(initRes.scan_id)
      setScanStatus('pending')
      setStatusMessage('Image accepted. Starting compliance pipeline...')

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
          Upload or capture packaged commodity images for Legal Metrology (Packaged Commodities) Rules, 2011 compliance verification.
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
        subtitle="Supported formats: JPEG, PNG, WebP (Max: 10MB)"
      >
        <div className="space-y-6">
          {/* File Dropzone Area */}
          {!selectedFile ? (
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
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files && e.target.files.length > 0) {
                    handleFileChange(e.target.files[0])
                  }
                }}
              />
              <div className="w-14 h-14 rounded-full bg-blue-50 text-brand-blue flex items-center justify-center mb-3 shadow-sm">
                <UploadCloud className="w-7 h-7" />
              </div>
              <h3 className="text-base font-semibold text-slate-800">
                Click to browse or drag and drop package image
              </h3>
              <p className="text-xs text-slate-400 max-w-sm text-center mt-1">
                Ensure packaging declarations (MRP, Net Quantity, Expiry, Manufacturer Address) are clearly visible and well-lit.
              </p>
              <div className="mt-4 flex items-center gap-2 text-xs text-slate-500 bg-white px-3 py-1.5 rounded-full border border-slate-200 shadow-2xs">
                <ScanLine className="w-3.5 h-3.5 text-brand-blue" />
                <span>Single-panel & multi-attribute verification supported</span>
              </div>
            </div>
          ) : (
            /* Selected File Preview Card */
            <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg flex flex-col sm:flex-row items-center gap-4">
              {previewUrl && (
                <img
                  src={previewUrl}
                  alt="Package Preview"
                  className="w-24 h-24 sm:w-32 sm:h-32 object-cover rounded-md border border-slate-300 shadow-2xs"
                />
              )}
              <div className="flex-1 space-y-1 text-center sm:text-left">
                <div className="flex items-center justify-center sm:justify-start gap-2">
                  <FileImage className="w-4 h-4 text-brand-blue" />
                  <span className="text-sm font-semibold text-slate-800 break-all">
                    {selectedFile.name}
                  </span>
                </div>
                <p className="text-xs text-slate-500">
                  Size: {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB • Type: {selectedFile.type}
                </p>
                <div className="pt-2">
                  <button
                    onClick={resetSelection}
                    disabled={isSubmitting}
                    className="text-xs text-red-600 hover:text-red-700 font-medium inline-flex items-center gap-1 disabled:opacity-50"
                  >
                    <X className="w-3.5 h-3.5" /> Remove & choose another image
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Optional Category Selector */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
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
                Running OpenCV quality check $\rightarrow$ Tesseract OCR $\rightarrow$ Gemini 3.6 Flash structured extraction $\rightarrow$ Rule engine audit.
              </p>
            </div>
          )}

          {/* Submission Action Bar */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
            {selectedFile && !isSubmitting && (
              <Button variant="outline" onClick={resetSelection}>
                Cancel
              </Button>
            )}
            <Button
              onClick={handleSubmitScan}
              disabled={!selectedFile || isSubmitting}
              icon={
                isSubmitting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <ArrowRight className="w-4 h-4" />
                )
              }
            >
              {isSubmitting ? 'Analyzing Package...' : 'Run Compliance Scan'}
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}

export default NewInspectionPage
