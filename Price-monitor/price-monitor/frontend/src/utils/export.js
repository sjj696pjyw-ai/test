import * as XLSX from 'xlsx'

export const exportToExcel = (data, filename) => {
  if (!data || data.length === 0) {
    console.error('No data to export')
    return
  }
  try {
    const worksheet = XLSX.utils.json_to_sheet(data)
    const workbook = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Report')
    
    // For browser environment
    const excelBuffer = XLSX.write(workbook, { bookType: 'xlsx', type: 'array' })
    const blob = new Blob([excelBuffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `${filename}.xlsx`
    link.click()
    URL.revokeObjectURL(link.href)
  } catch (error) {
    console.error('Excel export error:', error)
  }
}
 
export const exportToCSV = (data, filename) => {
  if (!data || data.length === 0) {
    console.error('No data to export')
    return
  }
  try {
    const worksheet = XLSX.utils.json_to_sheet(data)
    const csv = XLSX.utils.sheet_to_csv(worksheet)
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `${filename}.csv`
    link.click()
    URL.revokeObjectURL(link.href)
  } catch (error) {
    console.error('CSV export error:', error)
  }
}
 
export const formatPrice = (price) => {
  if (price == null) return 'N/A'
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB'
  }).format(price)
}

export const formatDate = (dateString) => {
  if (!dateString) return 'N/A'
  const date = new Date(dateString)
  return new Intl.DateTimeFormat('ru-RU', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  }).format(date)
}
