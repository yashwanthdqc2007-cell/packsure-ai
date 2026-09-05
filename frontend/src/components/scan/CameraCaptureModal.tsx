import React, { useEffect, useRef, useState, useCallback } from 'react'
import { Camera, X, RefreshCw, CheckCircle2, ShieldAlert } from 'lucide-react'
import Button from '../common/Button'

export interface CameraCaptureModalProps {
  isOpen: boolean
  onClose: () => void
  onCapture: (file: File) => void
}

export const CameraCaptureModal: React.FC<CameraCaptureModalProps> = ({
  isOpen,
  onClose,
  onCapture,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isInitializing, setIsInitializing] = useState(false)

  // Explicit track stoppage
  const stopCameraStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => {
        track.stop()
      })
      streamRef.current = null
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null
    }
    setIsStreaming(false)
    setIsInitializing(false)
  }, [])

  const startCameraStream = useCallback(async () => {
    setErrorMessage(null)
    setIsStreaming(false)
    setIsInitializing(true)

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setErrorMessage(
        'Camera capture is not supported by this browser. Please use Choose Image instead.'
      )
      setIsInitializing(false)
      return
    }

    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: 'environment' },
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
        audio: false,
      })

      streamRef.current = mediaStream

      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream
        videoRef.current.onloadedmetadata = () => {
          videoRef.current
            ?.play()
            .then(() => {
              setIsStreaming(true)
              setIsInitializing(false)
            })
            .catch(() => {
              setIsStreaming(true)
              setIsInitializing(false)
            })
        }
      }
    } catch (err: unknown) {
      setIsInitializing(false)
      const error = err as { name?: string; message?: string }
      if (
        error.name === 'NotAllowedError' ||
        error.name === 'PermissionDeniedError'
      ) {
        setErrorMessage(
          'Camera access was denied. Please allow camera permission or use Choose Image instead.'
        )
      } else if (
        error.name === 'NotFoundError' ||
        error.name === 'DevicesNotFoundError'
      ) {
        setErrorMessage(
          'Camera is unavailable on this device. Please use Choose Image instead.'
        )
      } else {
        setErrorMessage(
          'Unable to access camera. Please allow camera permission or use Choose Image instead.'
        )
      }
    }
  }, [])

  // Start on open, stop on close or unmount
  useEffect(() => {
    if (isOpen) {
      startCameraStream()
    } else {
      stopCameraStream()
    }

    return () => {
      stopCameraStream()
    }
  }, [isOpen, startCameraStream, stopCameraStream])

  const handleCapture = () => {
    if (!videoRef.current || !isStreaming) return

    const video = videoRef.current
    const canvas = document.createElement('canvas')
    const width = video.videoWidth || 1280
    const height = video.videoHeight || 720
    canvas.width = width
    canvas.height = height

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.drawImage(video, 0, 0, width, height)

    canvas.toBlob(
      (blob) => {
        if (blob) {
          const timestamp = Date.now()
          const file = new File([blob], `package-photo-${timestamp}.jpg`, {
            type: 'image/jpeg',
          })
          stopCameraStream()
          onCapture(file)
          onClose()
        }
      },
      'image/jpeg',
      0.92
    )
  }

  const handleCancel = () => {
    stopCameraStream()
    onClose()
  }

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/80 backdrop-blur-xs animate-in fade-in duration-150"
      role="dialog"
      aria-modal="true"
      aria-labelledby="camera-modal-title"
    >
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-xl w-full overflow-hidden flex flex-col">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <div>
            <h3
              id="camera-modal-title"
              className="text-base font-bold text-slate-900 leading-tight"
            >
              Capture Package Image
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Live camera preview for package inspection
            </p>
          </div>
          <button
            type="button"
            onClick={handleCancel}
            className="p-1.5 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100 transition-colors"
            title="Close camera"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Video Viewport Area */}
        <div className="relative bg-slate-950 flex items-center justify-center overflow-hidden min-h-[320px] max-h-[440px]">
          {/* Live Video Element */}
          <video
            ref={videoRef}
            playsInline
            muted
            autoPlay
            className={`w-full h-full object-contain max-h-[400px] ${
              !isStreaming ? 'hidden' : 'block'
            }`}
          />

          {/* Initializing State */}
          {isInitializing && !errorMessage && (
            <div className="flex flex-col items-center justify-center text-slate-400 p-8 text-center space-y-3">
              <RefreshCw className="w-8 h-8 animate-spin text-brand-blue" />
              <p className="text-xs font-medium">Connecting to camera...</p>
            </div>
          )}

          {/* Error Banner Inside Viewport */}
          {errorMessage && (
            <div className="p-8 text-center max-w-md mx-auto space-y-3">
              <div className="w-12 h-12 rounded-full bg-red-950/80 text-red-400 border border-red-800 flex items-center justify-center mx-auto">
                <ShieldAlert className="w-6 h-6" />
              </div>
              <p className="text-xs font-semibold text-red-400">
                Camera Access Error
              </p>
              <p className="text-xs text-slate-300 leading-relaxed">
                {errorMessage}
              </p>
              <div className="pt-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={startCameraStream}
                  icon={<RefreshCw className="w-3.5 h-3.5" />}
                >
                  Retry Camera
                </Button>
              </div>
            </div>
          )}

          {/* Alignment Target Overlay Guide */}
          {isStreaming && (
            <div className="absolute inset-0 pointer-events-none p-8 flex flex-col items-center justify-between">
              {/* Top Status */}
              <div className="self-start">
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-700/60 backdrop-blur-xs">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  Camera ready
                </span>
              </div>

              {/* Centered Target Frame */}
              <div className="w-64 sm:w-80 h-48 sm:h-56 border-2 border-dashed border-white/60 rounded-xl relative">
                {/* Corner indicators */}
                <div className="absolute -top-1 -left-1 w-4 h-4 border-t-2 border-l-2 border-brand-blue" />
                <div className="absolute -top-1 -right-1 w-4 h-4 border-t-2 border-r-2 border-brand-blue" />
                <div className="absolute -bottom-1 -left-1 w-4 h-4 border-b-2 border-l-2 border-brand-blue" />
                <div className="absolute -bottom-1 -right-1 w-4 h-4 border-b-2 border-r-2 border-brand-blue" />
              </div>

              {/* Bottom Instruction Pill */}
              <div className="bg-slate-900/80 text-slate-300 text-[11px] px-3 py-1 rounded-full border border-slate-700/80 backdrop-blur-xs">
                Position the package label clearly inside the frame.
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer Actions */}
        <div className="px-6 py-4 bg-slate-50 border-t border-slate-200 flex items-center justify-between gap-3">
          <p className="text-xs text-slate-500 hidden sm:block">
            High-resolution frame will be captured for OCR extraction.
          </p>

          <div className="flex items-center gap-3 ml-auto">
            <Button
              type="button"
              variant="outline"
              onClick={handleCancel}
            >
              Cancel
            </Button>

            <Button
              type="button"
              disabled={!isStreaming}
              onClick={handleCapture}
              icon={<Camera className="w-4 h-4" />}
            >
              Capture Photo
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default CameraCaptureModal
