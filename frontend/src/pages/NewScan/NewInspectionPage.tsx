import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Card from '../../components/common/Card'
import Button from '../../components/common/Button'
import ImageDropzone from '../../components/scan/ImageDropzone'
import ImageQualityPanel from '../../components/scan/ImageQualityPanel'
import InspectionDetailsForm from '../../components/scan/InspectionDetailsForm'
import { ArrowRight, RotateCcw } from 'lucide-react'

export const NewInspectionPage: React.FC = () => {
  const navigate = useNavigate()

  // State management
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null)
  const [category, setCategory] = useState<string>('')
  const [productName, setProductName] = useState<string>('')

  // Cleanup object URLs to prevent memory leaks
  useEffect(() => {
    return () => {
      if (imagePreviewUrl) {
        URL.revokeObjectURL(imagePreviewUrl)
      }
    }
  }, [imagePreviewUrl])

  const handleImageSelected = (file: File) => {
    // Revoke previous URL if any
    if (imagePreviewUrl) {
      URL.revokeObjectURL(imagePreviewUrl)
    }
    const newUrl = URL.createObjectURL(file)
    setImageFile(file)
    setImagePreviewUrl(newUrl)
  }

  const handleImageRemoved = () => {
    if (imagePreviewUrl) {
      URL.revokeObjectURL(imagePreviewUrl)
    }
    setImageFile(null)
    setImagePreviewUrl(null)
  }

  const handleClear = () => {
    handleImageRemoved()
    setCategory('')
    setProductName('')
  }

  // CTA is enabled only when both image AND category are selected
  const isFormValid = Boolean(imageFile && category.trim())

  const handleAnalyze = () => {
    if (!isFormValid) return
    navigate('/processing/demo-1')
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
          New Inspection
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Upload a package image to begin evidence-based compliance analysis.
        </p>
      </div>

      {/* Main Two-Column Setup Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Panel: Package Image (7 cols on desktop) */}
        <div className="lg:col-span-7 space-y-6">
          <Card
            title="Package Image"
            subtitle="Upload a clear image of the packaged commodity label or package surface."
          >
            <div className="space-y-6">
              {/* Drag and Drop Zone & Image Preview */}
              <ImageDropzone
                imageFile={imageFile}
                imagePreviewUrl={imagePreviewUrl}
                onImageSelected={handleImageSelected}
                onImageRemoved={handleImageRemoved}
              />

              {/* Image Quality Checks */}
              <ImageQualityPanel hasImage={Boolean(imageFile)} />
            </div>
          </Card>
        </div>

        {/* Right Panel: Inspection Details & How It Works (5 cols on desktop) */}
        <div className="lg:col-span-5 space-y-6">
          <Card
            title="Inspection Details"
            subtitle="Configure commodity classification and metadata."
          >
            <InspectionDetailsForm
              category={category}
              productName={productName}
              onCategoryChange={setCategory}
              onProductNameChange={setProductName}
            />
          </Card>
        </div>
      </div>

      {/* Bottom Action Area */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t border-slate-200">
        <div className="text-xs text-slate-500">
          {!isFormValid ? (
            <span className="text-amber-700 bg-amber-50 px-2.5 py-1 rounded border border-amber-200">
              Please select a package image and product category to proceed.
            </span>
          ) : (
            <span className="text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded border border-emerald-200">
              Ready for extraction and deterministic rule evaluation.
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto justify-end">
          <Button
            type="button"
            variant="secondary"
            onClick={handleClear}
            icon={<RotateCcw className="w-4 h-4" />}
          >
            Clear
          </Button>

          <Button
            type="button"
            disabled={!isFormValid}
            onClick={handleAnalyze}
            icon={<ArrowRight className="w-4 h-4" />}
          >
            Analyze Package
          </Button>
        </div>
      </div>
    </div>
  )
}

export default NewInspectionPage
