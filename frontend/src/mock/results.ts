export type ComplianceStatus = 'PASS' | 'FAIL' | 'REVIEW'

export interface EvidenceRegion {
  id: string
  label: string
  top: number // percentage
  left: number // percentage
  width: number // percentage
  height: number // percentage
}

export interface ComplianceFinding {
  id: string
  field: string
  status: ComplianceStatus
  detectedValue: string
  confidence: number // Evidence confidence percentage 0-100
  rule: string
  requirement: string
  explanation: string
  evidenceRegion: string // e.g. "Package image → region 01"
  regionCoords: EvidenceRegion
}

export interface InspectionResultData {
  id: string
  inspectionNumber: string
  product: string
  category: string
  ruleSet: string
  analysisMode: string
  findings: ComplianceFinding[]
}

// TODO: Replace with GET /api/v1/inspections/:id/results response from backend
export const mockInspectionResult: InspectionResultData = {
  id: 'demo-1',
  inspectionNumber: 'DEMO-001',
  product: 'Golden Harvest Rice',
  category: 'Food Grains',
  ruleSet: 'Applicable Legal Metrology requirements',
  analysisMode: 'Evidence-based inspection',
  findings: [
    {
      id: 'f-1',
      field: 'MRP',
      status: 'PASS',
      detectedValue: '₹ 495.00 (Incl. of all taxes)',
      confidence: 98,
      rule: 'MRP declaration detected',
      requirement: 'Maximum Retail Price declaration inclusive of all taxes',
      explanation: 'Unambiguous retail price declaration with tax inclusion phrase detected on principal display panel.',
      evidenceRegion: 'Package image → region 01',
      regionCoords: {
        id: 'reg-mrp',
        label: 'MRP',
        top: 38,
        left: 20,
        width: 60,
        height: 7,
      },
    },
    {
      id: 'f-2',
      field: 'Net Quantity',
      status: 'PASS',
      detectedValue: 'Net Quantity 5 kg',
      confidence: 96,
      rule: 'Net quantity declaration detected',
      requirement: 'Net quantity in standard metric units with approved font size ratio',
      explanation: 'Net weight declared in approved metric unit (kg) with compliant numeral dimensions.',
      evidenceRegion: 'Package image → region 02',
      regionCoords: {
        id: 'reg-qty',
        label: 'Net Quantity',
        top: 31,
        left: 20,
        width: 60,
        height: 7,
      },
    },
    {
      id: 'f-3',
      field: 'Consumer Care',
      status: 'FAIL',
      detectedValue: 'Not detected',
      confidence: 94,
      rule: 'Consumer care contact declaration',
      requirement: 'Consumer care contact declaration with name, address, telephone & email',
      explanation: 'No consumer-care contact information was detected in the available package evidence.',
      evidenceRegion: 'Package image → region 03',
      regionCoords: {
        id: 'reg-care',
        label: 'Consumer Care',
        top: 60,
        left: 20,
        width: 60,
        height: 8,
      },
    },
    {
      id: 'f-4',
      field: 'Manufacturer / Packer',
      status: 'REVIEW',
      detectedValue: 'Harvest Agro Foods India Pvt. Ltd.',
      confidence: 71,
      rule: 'Manufacturer / packer declaration',
      requirement: 'Complete name and physical address of manufacturer or packer',
      explanation: 'Text is partially visible and requires inspector verification.',
      evidenceRegion: 'Package image → region 04',
      regionCoords: {
        id: 'reg-mfg',
        label: 'Manufacturer / Packer',
        top: 52,
        left: 20,
        width: 60,
        height: 8,
      },
    },
    {
      id: 'f-5',
      field: 'Country of Origin',
      status: 'PASS',
      detectedValue: 'India',
      confidence: 97,
      rule: 'Country of origin where applicable',
      requirement: 'Clear statement of Country of Origin on packaged commodity',
      explanation: 'Country of manufacture/origin clearly identified as India.',
      evidenceRegion: 'Package image → region 05',
      regionCoords: {
        id: 'reg-origin',
        label: 'Country of Origin',
        top: 14,
        left: 20,
        width: 60,
        height: 7,
      },
    },
  ],
}
