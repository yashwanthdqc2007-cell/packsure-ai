export interface MetricData {
  title: string
  value: number | string
  changeText: string
  status?: 'PASS' | 'FAIL' | 'REVIEW' | 'INFO'
}

export interface ActivityDay {
  day: string
  scans: number
  compliant: number
  nonCompliant: number
  needsReview: number
}

export interface RecentInspection {
  id: string
  product: string
  category: string
  scannedAt: string
  result: 'PASS' | 'FAIL' | 'REVIEW'
  score: number
}

export const mockDashboardMetrics: MetricData[] = [
  {
    title: 'Total Scans',
    value: 128,
    changeText: '+12 this week',
    status: 'INFO',
  },
  {
    title: 'Compliant',
    value: 76,
    changeText: '59.4% of scans',
    status: 'PASS',
  },
  {
    title: 'Non-Compliant',
    value: 34,
    changeText: '26.6% of scans',
    status: 'FAIL',
  },
  {
    title: 'Needs Review',
    value: 18,
    changeText: '14.0% of scans',
    status: 'REVIEW',
  },
]

export const mockWeeklyActivity: ActivityDay[] = [
  { day: 'Mon', scans: 14, compliant: 9, nonCompliant: 3, needsReview: 2 },
  { day: 'Tue', scans: 18, compliant: 11, nonCompliant: 5, needsReview: 2 },
  { day: 'Wed', scans: 16, compliant: 10, nonCompliant: 4, needsReview: 2 },
  { day: 'Thu', scans: 22, compliant: 13, nonCompliant: 6, needsReview: 3 },
  { day: 'Fri', scans: 25, compliant: 16, nonCompliant: 6, needsReview: 3 },
  { day: 'Sat', scans: 19, compliant: 11, nonCompliant: 5, needsReview: 3 },
  { day: 'Sun', scans: 14, compliant: 6, nonCompliant: 5, needsReview: 3 },
]

export const mockRecentInspections: RecentInspection[] = [
  {
    id: 'demo-1',
    product: 'SunFresh Refined Sunflower Oil',
    category: 'Edible Oil',
    scannedAt: 'Today, 10:42 AM',
    result: 'PASS',
    score: 96,
  },
  {
    id: 'demo-2',
    product: 'Golden Harvest Rice',
    category: 'Food Grains',
    scannedAt: 'Today, 09:18 AM',
    result: 'FAIL',
    score: 68,
  },
  {
    id: 'demo-3',
    product: 'PureDrop Mineral Water',
    category: 'Packaged Water',
    scannedAt: 'Yesterday, 04:32 PM',
    result: 'REVIEW',
    score: 74,
  },
  {
    id: 'demo-4',
    product: 'DailyChoice Sugar',
    category: 'Food Grains',
    scannedAt: 'Yesterday, 02:15 PM',
    result: 'PASS',
    score: 94,
  },
  {
    id: 'demo-5',
    product: 'FreshBake Atta',
    category: 'Flour',
    scannedAt: 'Yesterday, 11:06 AM',
    result: 'FAIL',
    score: 61,
  },
]
