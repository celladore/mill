// Sample API client for the frontend
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:7071/api';

/**
 * Client for interacting with the Mill API
 */
class MillClient {
  /**
   * Convert a LaTeX file to PDF
   * @param file - The LaTeX file to convert
   * @returns The conversion result
   */
  async convertLatex(file: File): Promise<any> {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch(`${API_BASE_URL}/conversion`, {
      method: 'POST',
      body: formData,
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    return response.json();
  }
  
  /**
   * Get the status of a conversion
   * @param conversionId - The ID of the conversion
   * @returns The conversion status
   */
  async getConversionStatus(conversionId: string): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/conversion/${conversionId}`, {
      method: 'GET',
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    return response.json();
  }
  
  /**
   * Download the converted PDF
   * @param pdfUrl - The URL of the PDF
   */
  downloadPdf(pdfUrl: string): void {
    // Create a URL that includes the API base if needed
    const fullUrl = pdfUrl.startsWith('http') ? pdfUrl : `${API_BASE_URL}${pdfUrl}`;
    window.open(fullUrl, '_blank');
  }
}

export default new MillClient();
