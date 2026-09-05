import React, { useRef, useState } from 'react'
import {
  UploadCloud,
  Camera,
  Image as ImageIcon,
  Trash2,
  RefreshCw,
  AlertCircle,
} from 'lucide-react'
import Button from '../common/Button'
import CameraCaptureModal from './CameraCaptureModal'

export interface ImageDropzoneProps {
  imageFile: File | null
  imagePreviewUrl: string | null
  onImageSelected: (file: File) => void
  onImageRemoved: () => void
}

const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10 MB

export const ImageDropzone: React.FC<ImageDropzoneProps> = ({
  imageFile,
  imagePreviewUrl,
  onImageSelected,
  onImageRemoved,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [isDragOver, setIsDragOver] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isCameraModalOpen, setIsCameraModalOpen] = useState(false)

  const validateAndProcessFile = (file: File) => {
    setErrorMessage(null)

    if (!file.type.startsWith('image/')) {
      setErrorMessage(
        'Unsupported file format. Please upload a JPG or PNG image.'
      )
      return
    }

    if (file.size > MAX_FILE_SIZE) {
      setErrorMessage(
        'File size exceeds 10 MB. Please choose a smaller package image.'
      )
      return
    }

    onImageSelected(file)
  }

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(true)
  }

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(false)
  }

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(false)

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const droppedFile = e.dataTransfer.files[0]
      validateAndProcessFile(droppedFile)
    }
  }

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const selectedFile = e.target.files[0]
      validateAndProcessFile(selectedFile)
    }
    // Reset file input so same file can be re-selected if removed
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const triggerFileInput = () => {
    fileInputRef.current?.click()
  }

  const handleOpenCamera = () => {
    setErrorMessage(null)
    setIsCameraModalOpen(true)
  }

  const handleCameraCapture = (file: File) => {
    validateAndProcessFile(file)
    setIsCameraModalOpen(false)
  }

  return (
    <div className="space-y-4">
      {/* Hidden native file input for Choose Image */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/jpg"
        className="hidden"
        onChange={handleFileInputChange}
      />

      {/* Camera Capture Modal using MediaDevices API */}
      <CameraCaptureModal
        isOpen={isCameraModalOpen}
        onClose={() => setIsCameraModalOpen(false)}
        onCapture={handleCameraCapture}
      />

      {/* Validation Error Alert */}
      {errorMessage && (
        <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
          <AlertCircle className="w-4 h-4 flex-shrink-0 text-red-600" />
          <span>{errorMessage}</span>
        </div>
      )}

      {!imagePreviewUrl ? (
        /* Empty Upload State / Drag & Drop Area */
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`relative border-2 border-dashed rounded-xl p-8 sm:p-12 text-center transition-all duration-150 flex flex-col items-center justify-center min-h-[340px] ${
            isDragOver
              ? 'border-brand-blue bg-blue-50/70 scale-[0.99]'
              : 'border-slate-300 hover:border-slate-400 bg-slate-50/50 hover:bg-slate-50'
          }`}
        >
          <div className="w-14 h-14 rounded-full bg-blue-50 text-brand-blue flex items-center justify-center mb-4 shadow-sm">
            <UploadCloud className="w-7 h-7" />
          </div>

          <h4 className="text-base font-semibold text-slate-800 tracking-tight">
            Drop package image here
          </h4>
          <p className="text-xs text-slate-500 mt-1 mb-5 max-w-xs">
            or choose an image from your device
          </p>

          <div className="flex flex-wrap items-center justify-center gap-3">
            <Button
              type="button"
              onClick={triggerFileInput}
              icon={<ImageIcon className="w-4 h-4" />}
            >
              Choose Image
            </Button>
            <Button
              type="button"
              variant="secondary"
              title="Open webcam or attached camera"
              icon={<Camera className="w-4 h-4" />}
              onClick={handleOpenCamera}
            >
              Open Camera
            </Button>
          </div>

          <p className="text-[11px] text-slate-400 font-medium mt-6">
            JPG, PNG • Max 10 MB
          </p>
        </div>
      ) : (
        /* Selected Image Preview State */
        <div className="border border-slate-200 rounded-xl overflow-hidden bg-slate-900 shadow-sm">
          <div className="relative group max-h-[380px] flex items-center justify-center bg-slate-950 p-2">
            <img
              src={imagePreviewUrl}
              alt="Uploaded package preview"
              className="max-h-[340px] w-auto max-w-full object-contain rounded"
            />
          </div>

          {/* Action Bar beneath preview */}
          <div className="bg-white p-4 border-t border-slate-200 flex items-center justify-between gap-4">
            <div className="min-w-0">
              <p className="text-xs font-semibold text-slate-800 truncate">
                {imageFile?.name || 'Selected Package Image'}
              </p>
              <p className="text-[11px] text-slate-400 mt-0.5">
                {imageFile
                  ? `${(imageFile.size / (1024 * 1024)).toFixed(2)} MB • ${imageFile.type}`
                  : 'Image ready for analysis'}
              </p>
            </div>

            <div className="flex items-center gap-2 flex-shrink-0">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={triggerFileInput}
                icon={<RefreshCw className="w-3.5 h-3.5" />}
              >
                Change image
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="text-red-600 hover:text-red-700 hover:bg-red-50 hover:border-red-200"
                onClick={onImageRemoved}
                icon={<Trash2 className="w-3.5 h-3.5" />}
              >
                Remove
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ImageDropzone
