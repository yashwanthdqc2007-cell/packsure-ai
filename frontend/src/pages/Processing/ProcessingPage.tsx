import React, { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import Card from '../../components/common/Card'
import Button from '../../components/common/Button'
import {
  ScanLine,
  FileSearch,
  Scale,
  ShieldCheck,
  CheckCircle2,
  Loader2,
  Clock,
  ArrowRight,
  LayoutDashboard,
  Eye,
  FileCheck2,
} from 'lucide-react'

// TODO: Replace simulated processing with backend scan job status.
// In future implementation, this component will poll /api/v1/inspections/:id/status
// or connect via WebSocket to receive real-time job execution telemetry.

interface StageConfig {
  id: string
  number: string
  title: string
  description: string
  icon: React.ReactNode
}

const PIPELINE_STAGES: StageConfig[] = [
  {
    id: 'preprocessing',
    number: '01',
    title: 'Image Preprocessing',
    description: 'Checking image quality and preparing visual evidence',
    icon: <ScanLine className="w-4 h-4" />,
  },
  {
    id: 'extraction',
    number: '02',
    title: 'Declaration Extraction',
    description: 'Extracting visible package declarations',
    icon: <FileSearch className="w-4 h-4" />,
  },
  {
    id: 'rules',
    number: '03',
    title: 'Rule Evaluation',
    description: 'Checking extracted evidence against applicable rules',
    icon: <Scale className="w-4 h-4" />,
  },
  {
    id: 'compilation',
    number: '04',
    title: 'Evidence Compilation',
    description: 'Linking findings to visual evidence and preparing results',
    icon: <ShieldCheck className="w-4 h-4" />,
  },
]

// Total simulation duration in milliseconds (~6.5 seconds)
const TOTAL_DURATION_MS = 6500

export const ProcessingPage: React.FC = () => {
  const { id = 'demo-1' } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()

  // Extract route state if passed from New Inspection flow
  const routeState = location.state as
    | {
        imagePreviewUrl?: string
        productName?: string
        category?: string
      }
    | undefined

  // State management
  const [progress, setProgress] = useState<number>(0)
  const [currentStageIndex, setCurrentStageIndex] = useState<number>(0)
  const [statusMessage, setStatusMessage] = useState<string>('Preparing image evidence...')
  const [isComplete, setIsComplete] = useState<boolean>(false)

  // Avoid duplicate execution on re-renders
  const startTimeRef = useRef<number | null>(null)
  const animationFrameRef = useRef<number | null>(null)

  useEffect(() => {
    startTimeRef.current = performance.now()

    const updateSimulation = (now: number) => {
      if (!startTimeRef.current) {
        startTimeRef.current = now
      }

      const elapsed = now - startTimeRef.current
      const rawProgress = Math.min(100, (elapsed / TOTAL_DURATION_MS) * 100)
      setProgress(Math.round(rawProgress))

      // Stage and Status Message transitions based on elapsed time:
      // Stage 1: 0 – 1600ms (0% - 25%)
      // Stage 2: 1600 – 3200ms (25% - 50%)
      // Stage 3: 3200 – 4800ms (50% - 75%)
      // Stage 4: 4800 – 6500ms (75% - 100%)
      if (elapsed < 800) {
        setCurrentStageIndex(0)
        setStatusMessage('Preparing image evidence...')
      } else if (elapsed < 1600) {
        setCurrentStageIndex(0)
        setStatusMessage('Checking image quality...')
      } else if (elapsed < 2400) {
        setCurrentStageIndex(1)
        setStatusMessage('Extracting visible declarations...')
      } else if (elapsed < 3200) {
        setCurrentStageIndex(1)
        setStatusMessage('Structuring detected evidence...')
      } else if (elapsed < 4800) {
        setCurrentStageIndex(2)
        setStatusMessage('Evaluating applicable requirements...')
      } else if (elapsed < 6500) {
        setCurrentStageIndex(3)
        setStatusMessage('Compiling inspection evidence...')
      } else {
        // Complete state
        setCurrentStageIndex(4)
        setProgress(100)
        setStatusMessage('Inspection analysis ready')
        setIsComplete(true)
        return
      }

      animationFrameRef.current = requestAnimationFrame(updateSimulation)
    }

    animationFrameRef.current = requestAnimationFrame(updateSimulation)

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
      }
    }
  }, [id])

  // Compute display values
  const formattedId =
    id.toLowerCase() === 'demo-1' ? 'DEMO-001' : id.toUpperCase().replace(/^SCAN-/, '')
  const displayProduct = routeState?.productName || 'Demo Package'
  const displayCategory = routeState?.category || 'Food Grains'
  const displayImage = routeState?.imagePreviewUrl || '/demo-package.svg'

  const handleViewResults = () => {
    navigate(`/results/${id || 'demo-1'}`)
  }

  const handleBackToDashboard = () => {
    navigate('/dashboard')
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-10">
      {/* PAGE HEADER */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              Inspection in Progress
            </h1>
            {!isComplete ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-brand-blue border border-blue-200">
                <span className="w-1.5 h-1.5 rounded-full bg-brand-blue animate-pulse" />
                Live Analysis
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Analysis Ready
              </span>
            )}
          </div>
          <p className="text-sm text-slate-500 mt-1">
            PackSure is analyzing package evidence and preparing a compliance assessment.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-center">
          <span className="text-xs font-mono text-slate-400 bg-slate-100 border border-slate-200 px-2.5 py-1 rounded">
            SIH26034
          </span>
          <span className="text-xs font-mono text-slate-600 bg-white border border-slate-200 px-2.5 py-1 rounded font-semibold">
            {formattedId}
          </span>
        </div>
      </div>

      {/* MAIN WORKSPACE GRID */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* LEFT COLUMN: PACKAGE PREVIEW & INSPECTION SUMMARY (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          {/* 1. PACKAGE PREVIEW CARD */}
          <Card
            title="Package Evidence"
            subtitle="Uploaded visual reference under legal metrology inspection"
            padding="none"
          >
            <div className="p-4 bg-slate-900 border-b border-slate-800">
              <div className="relative rounded-lg overflow-hidden bg-slate-950 flex items-center justify-center min-h-[300px] border border-slate-800">
                {/* Visual HUD Reticle Overlay */}
                <div className="absolute inset-0 pointer-events-none z-10 flex flex-col justify-between p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-mono font-bold tracking-wider px-2 py-0.5 rounded bg-blue-600/90 text-white backdrop-blur-sm border border-blue-400/40">
                      PACKAGE EVIDENCE
                    </span>
                    <span className="text-[10px] font-mono text-slate-300 px-1.5 py-0.5 rounded bg-slate-900/80 backdrop-blur-sm border border-slate-700">
                      SIH26034
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
                    <span className="bg-slate-900/80 px-1.5 py-0.5 rounded border border-slate-800">
                      Demo Inspection
                    </span>
                    <span className="bg-slate-900/80 px-1.5 py-0.5 rounded border border-slate-800 flex items-center gap-1">
                      <Eye className="w-3 h-3 text-brand-blue" />
                      Visual Record
                    </span>
                  </div>
                </div>

                {/* Package Image or Polished Placeholder */}
                {displayImage ? (
                  <img
                    src={displayImage}
                    alt="Package evidence preview"
                    className="max-h-[300px] w-full object-contain p-2"
                  />
                ) : (
                  <div className="flex flex-col items-center justify-center p-8 text-center text-slate-400">
                    <ScanLine className="w-12 h-12 text-slate-600 mb-2 stroke-1" />
                    <p className="text-xs font-medium text-slate-300">Package Evidence Frame</p>
                    <p className="text-[11px] text-slate-500 mt-0.5">Demo Inspection • SIH26034</p>
                  </div>
                )}
              </div>
            </div>

            {/* Evidence details beneath preview */}
            <div className="p-4 bg-white flex items-center justify-between text-xs text-slate-600">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                <span className="font-medium text-slate-800">Evidence Frame Captured</span>
              </div>
              <span className="font-mono text-slate-400">Ready for Audit</span>
            </div>
          </Card>

          {/* 5. INSPECTION SUMMARY CARD */}
          <Card
            title="Inspection Summary"
            subtitle="Metadata and operational parameters"
            padding="sm"
          >
            <div className="divide-y divide-slate-100 text-xs">
              <div className="py-2.5 flex items-center justify-between">
                <span className="text-slate-500">Inspection ID:</span>
                <span className="font-mono font-semibold text-slate-900">{formattedId}</span>
              </div>
              <div className="py-2.5 flex items-center justify-between">
                <span className="text-slate-500">Product:</span>
                <span className="font-medium text-slate-900">{displayProduct}</span>
              </div>
              <div className="py-2.5 flex items-center justify-between">
                <span className="text-slate-500">Category:</span>
                <span className="font-medium text-slate-900">{displayCategory}</span>
              </div>
              <div className="py-2.5 flex items-center justify-between">
                <span className="text-slate-500">Analysis Mode:</span>
                <span className="font-medium text-slate-900">Evidence-based inspection</span>
              </div>
              <div className="py-2.5 flex items-center justify-between">
                <span className="text-slate-500">Status:</span>
                {isComplete ? (
                  <span className="inline-flex items-center gap-1 font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Complete
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 font-semibold text-brand-blue bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Processing
                  </span>
                )}
              </div>
            </div>
          </Card>
        </div>

        {/* RIGHT COLUMN: PROCESSING PIPELINE & COMPLETION STATE (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          <Card
            title="Processing Pipeline"
            subtitle="Deterministic verification and evidence structuring stages"
          >
            <div className="space-y-6">
              {/* 4. STATUS MESSAGE & 3. PROGRESS INDICATOR */}
              <div className="bg-slate-50 rounded-lg p-4 border border-slate-200 space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    {!isComplete ? (
                      <Loader2 className="w-4 h-4 text-brand-blue animate-spin flex-shrink-0" />
                    ) : (
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                    )}
                    <span className="text-sm font-semibold text-slate-800 truncate">
                      {statusMessage}
                    </span>
                  </div>
                  <span className="font-mono text-sm font-bold text-slate-900 flex-shrink-0">
                    {progress}%
                  </span>
                </div>

                {/* Overall Smooth Animated Progress Bar */}
                <div className="w-full bg-slate-200 h-2.5 rounded-full overflow-hidden">
                  <div
                    className={`h-full transition-all duration-300 ease-out ${
                      isComplete ? 'bg-emerald-600' : 'bg-brand-blue'
                    }`}
                    style={{ width: `${progress}%` }}
                  />
                </div>

                {/* Pipeline Milestones */}
                <div className="grid grid-cols-4 gap-1 text-[11px] font-mono text-slate-400 pt-0.5 text-center">
                  <span className={progress >= 25 ? 'text-brand-blue font-medium' : ''}>01 Prep</span>
                  <span className={progress >= 50 ? 'text-brand-blue font-medium' : ''}>02 Extract</span>
                  <span className={progress >= 75 ? 'text-brand-blue font-medium' : ''}>03 Rules</span>
                  <span className={progress >= 100 ? 'text-emerald-700 font-medium' : ''}>04 Ready</span>
                </div>
              </div>

              {/* 2. PROCESSING PIPELINE STAGES */}
              <div className="space-y-3">
                {PIPELINE_STAGES.map((stage, idx) => {
                  // Determine status for each stage: WAITING | PROCESSING | COMPLETE
                  let stageStatus: 'WAITING' | 'PROCESSING' | 'COMPLETE' = 'WAITING'

                  if (isComplete || idx < currentStageIndex) {
                    stageStatus = 'COMPLETE'
                  } else if (idx === currentStageIndex) {
                    stageStatus = 'PROCESSING'
                  } else {
                    stageStatus = 'WAITING'
                  }

                  return (
                    <div
                      key={stage.id}
                      className={`flex items-center justify-between p-3.5 rounded-lg border transition-all duration-200 ${
                        stageStatus === 'PROCESSING'
                          ? 'bg-blue-50/70 border-blue-200 text-slate-900 shadow-sm ring-1 ring-blue-100'
                          : stageStatus === 'COMPLETE'
                          ? 'bg-slate-50/70 border-slate-200 text-slate-800'
                          : 'bg-white border-slate-100 text-slate-400 opacity-60'
                      }`}
                    >
                      <div className="flex items-start sm:items-center gap-3.5 min-w-0">
                        {/* Number Badge or Icon */}
                        <div
                          className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold flex-shrink-0 transition-colors ${
                            stageStatus === 'COMPLETE'
                              ? 'bg-emerald-100 text-emerald-700'
                              : stageStatus === 'PROCESSING'
                              ? 'bg-blue-600 text-white'
                              : 'bg-slate-100 text-slate-400'
                          }`}
                        >
                          {stageStatus === 'COMPLETE' ? (
                            <CheckCircle2 className="w-4 h-4 text-emerald-700" />
                          ) : (
                            stage.number
                          )}
                        </div>

                        {/* Title & Description */}
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span
                              className={`text-sm font-semibold tracking-tight ${
                                stageStatus === 'PROCESSING'
                                  ? 'text-slate-900'
                                  : stageStatus === 'COMPLETE'
                                  ? 'text-slate-800'
                                  : 'text-slate-500'
                              }`}
                            >
                              {stage.title}
                            </span>
                          </div>
                          <p className="text-xs text-slate-500 mt-0.5 truncate">
                            {stage.description}
                          </p>
                        </div>
                      </div>

                      {/* Stage State Badge */}
                      <div className="flex-shrink-0 ml-3">
                        {stageStatus === 'COMPLETE' && (
                          <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded-md">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            Complete
                          </span>
                        )}
                        {stageStatus === 'PROCESSING' && (
                          <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-brand-blue bg-white border border-blue-200 px-2.5 py-1 rounded-md shadow-sm">
                            <Loader2 className="w-3.5 h-3.5 animate-spin text-brand-blue" />
                            Processing
                          </span>
                        )}
                        {stageStatus === 'WAITING' && (
                          <span className="inline-flex items-center gap-1 text-xs font-medium text-slate-400 bg-slate-50 border border-slate-200 px-2.5 py-1 rounded-md">
                            <Clock className="w-3.5 h-3.5" />
                            Waiting
                          </span>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* 6. COMPLETION STATE & ACTION BUTTONS */}
              {isComplete ? (
                <div className="pt-4 border-t border-slate-200 space-y-4 animate-fadeIn">
                  {/* Success State Callout */}
                  <div className="bg-emerald-50/80 border border-emerald-200 rounded-xl p-4 flex items-start gap-3.5">
                    <div className="w-9 h-9 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-700 flex-shrink-0 mt-0.5">
                      <FileCheck2 className="w-5 h-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h4 className="text-sm font-semibold text-emerald-900">
                        Inspection analysis ready
                      </h4>
                      <p className="text-xs text-emerald-700 mt-0.5">
                        Your evidence-based compliance assessment is ready for review.
                      </p>
                    </div>
                  </div>

                  {/* Primary & Secondary Action Buttons */}
                  <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-1">
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={handleBackToDashboard}
                      icon={<LayoutDashboard className="w-4 h-4" />}
                      className="w-full sm:w-auto"
                    >
                      Back to Dashboard
                    </Button>

                    <Button
                      type="button"
                      onClick={handleViewResults}
                      icon={<ArrowRight className="w-4 h-4" />}
                      className="w-full sm:w-auto font-semibold px-6"
                    >
                      View Inspection Results
                    </Button>
                  </div>
                </div>
              ) : (
                /* Pending state indicator */
                <div className="pt-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-400">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-brand-blue animate-ping" />
                    <span>Executing deterministic pipeline sequence...</span>
                  </div>
                  <span className="font-mono text-[11px]">Est. ~6s</span>
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}

export default ProcessingPage
