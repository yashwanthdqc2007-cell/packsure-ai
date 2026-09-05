import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Card from '../../components/common/Card'
import Button from '../../components/common/Button'
import {
  ScanLine,
  CheckCircle2,
  FileSearch,
  Scale,
  ArrowRight,
  ShieldCheck,
} from 'lucide-react'

export const ProcessingPage: React.FC = () => {
  const { id = 'demo-1' } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [currentStep, setCurrentStep] = useState(1)

  useEffect(() => {
    const timer1 = setTimeout(() => setCurrentStep(2), 1200)
    const timer2 = setTimeout(() => setCurrentStep(3), 2400)
    const timer3 = setTimeout(() => setCurrentStep(4), 3600)

    return () => {
      clearTimeout(timer1)
      clearTimeout(timer2)
      clearTimeout(timer3)
    }
  }, [])

  const steps = [
    {
      num: 1,
      title: 'Image Preprocessing',
      desc: 'Adaptive thresholding, contrast normalization & noise reduction',
      icon: <ScanLine className="w-4 h-4" />,
    },
    {
      num: 2,
      title: 'Declaration Extraction',
      desc: 'OCR text recognition & Gemini vision model structuring',
      icon: <FileSearch className="w-4 h-4" />,
    },
    {
      num: 3,
      title: 'Deterministic Rule Evaluation',
      desc: 'Legal Metrology (Packaged Commodities) Rules, 2011 checks',
      icon: <Scale className="w-4 h-4" />,
    },
    {
      num: 4,
      title: 'Evidence Compilation',
      desc: 'Generating compliance score, violation citations & audit breakdown',
      icon: <ShieldCheck className="w-4 h-4" />,
    },
  ]

  return (
    <div className="max-w-2xl mx-auto py-8 space-y-6">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
          Processing Inspection #{id.toUpperCase()}
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Evaluating package declarations against Legal Metrology Rules, 2011
        </p>
      </div>

      <Card padding="lg" className="border-slate-200">
        <div className="space-y-6">
          {/* Animated Spinner/Pulse Icon */}
          <div className="flex justify-center">
            <div className="relative">
              <div className="w-16 h-16 rounded-full bg-blue-50 border border-blue-100 flex items-center justify-center text-brand-blue animate-pulse">
                <ScanLine className="w-8 h-8" />
              </div>
            </div>
          </div>

          {/* Progress Steps */}
          <div className="space-y-3 pt-2">
            {steps.map((step) => {
              const isCompleted = currentStep > step.num
              const isCurrent = currentStep === step.num

              return (
                <div
                  key={step.num}
                  className={`flex items-center justify-between p-3.5 rounded-lg border transition-all duration-200 ${
                    isCurrent
                      ? 'bg-blue-50/60 border-blue-200 text-slate-900'
                      : isCompleted
                      ? 'bg-slate-50/50 border-slate-200 text-slate-700'
                      : 'bg-white border-slate-100 text-slate-400 opacity-60'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold ${
                        isCompleted
                          ? 'bg-emerald-100 text-emerald-700'
                          : isCurrent
                          ? 'bg-brand-blue text-white animate-spin'
                          : 'bg-slate-100 text-slate-400'
                      }`}
                    >
                      {isCompleted ? <CheckCircle2 className="w-4 h-4" /> : step.num}
                    </div>
                    <div>
                      <div className="text-sm font-semibold">{step.title}</div>
                      <div className="text-[11px] text-slate-500">{step.desc}</div>
                    </div>
                  </div>

                  <div>
                    {isCompleted && (
                      <span className="text-xs font-medium text-emerald-600">Done</span>
                    )}
                    {isCurrent && (
                      <span className="text-xs font-medium text-brand-blue animate-pulse">
                        Analyzing...
                      </span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>

          {/* Action to view results */}
          <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
            <span className="text-xs text-slate-400 font-mono">
              Pipeline: Tesseract + Gemini Vision + Rules Engine
            </span>
            <Button
              onClick={() => navigate(`/results/${id}`)}
              icon={<ArrowRight className="w-4 h-4" />}
            >
              View Inspection Results
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}

export default ProcessingPage
