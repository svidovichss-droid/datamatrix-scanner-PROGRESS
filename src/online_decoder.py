"""
Online DataMatrix decoders - supports multiple online decoding services.
Author: А. Свидович / А. Петляков для PROGRESS
"""
import base64
import io
import requests
from typing import Optional, Tuple
import cv2
import numpy as np


class OnlineDecoderResult:
    """Result from an online decoder."""
    def __init__(self, success: bool, data: str = "", error: str = "", 
                 service: str = ""):
        self.success = success
        self.data = data
        self.error = error
        self.service = service


class OnlineDataMatrixDecoder:
    """
    Online DataMatrix decoder using various web services.
    Provides fallback options when local decoding fails.
    """
    
    # Available online decoder services
    SERVICES = {
        'inlite': 'https://www.inliteresearch.com/free-online-barcode-decoder/',
        'zxing': 'https://zxing.org/w/decode.jspx',
        'barcode': 'https://barcode.tec-it.com/ru/DataMatrix',
    }
    
    def __init__(self, timeout: int = 10):
        """
        Initialize online decoder.
        
        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def decode_with_zxing(self, image: np.ndarray) -> OnlineDecoderResult:
        """
        Decode using ZXing online service.
        
        Args:
            image: Image containing DataMatrix code
            
        Returns:
            OnlineDecoderResult with decoded data or error
        """
        try:
            # Convert image to JPEG bytes
            _, img_encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 80])
            img_bytes = img_encoded.tobytes()
            
            # ZXing accepts multipart form data
            files = {'file': ('image.jpg', io.BytesIO(img_bytes), 'image/jpeg')}
            
            response = self.session.post(
                'https://zxing.org/w/decode',
                files=files,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                html = response.text
                
                # Parse result from HTML
                # Look for "Raw text" or "Text" in the response
                if 'Raw text' in html or 'Текст' in html:
                    # Extract decoded text from HTML
                    decoded = self._extract_zxing_result(html)
                    if decoded:
                        return OnlineDecoderResult(
                            success=True,
                            data=decoded,
                            service='zxing'
                        )
                
                return OnlineDecoderResult(
                    success=False,
                    error="No DataMatrix found",
                    service='zxing'
                )
            else:
                return OnlineDecoderResult(
                    success=False,
                    error=f"HTTP {response.status_code}",
                    service='zxing'
                )
                
        except requests.Timeout:
            return OnlineDecoderResult(
                success=False,
                error="Request timeout",
                service='zxing'
            )
        except Exception as e:
            return OnlineDecoderResult(
                success=False,
                error=str(e),
                service='zxing'
            )
    
    def _extract_zxing_result(self, html: str) -> Optional[str]:
        """Extract decoded text from ZXing HTML response."""
        try:
            # Look for the result in common patterns
            import re
            
            # Pattern 1: Raw text value
            match = re.search(r'Raw text.*?<td[^>]*>(.*?)</td>', html, re.DOTALL)
            if match:
                text = match.group(1).strip()
                text = re.sub(r'<[^>]+>', '', text)  # Remove HTML tags
                if text and len(text) > 0:
                    return text
            
            # Pattern 2: Text field
            match = re.search(r'Text.*?<td[^>]*>(.*?)</td>', html, re.DOTALL)
            if match:
                text = match.group(1).strip()
                text = re.sub(r'<[^>]+>', '', text)
                if text and len(text) > 0:
                    return text
            
            # Pattern 3: Russian "Текст"
            match = re.search(r'Текст.*?<td[^>]*>(.*?)</td>', html, re.DOTALL | re.UNICODE)
            if match:
                text = match.group(1).strip()
                text = re.sub(r'<[^>]+>', '', text)
                if text and len(text) > 0:
                    return text
                    
        except Exception:
            pass
        
        return None
    
    def decode_with_inlite(self, image: np.ndarray) -> OnlineDecoderResult:
        """
        Decode using Inlite Research online service.
        
        Args:
            image: Image containing DataMatrix code
            
        Returns:
            OnlineDecoderResult with decoded data or error
        """
        try:
            # Convert image to base64
            _, img_encoded = cv2.imencode('.png', image)
            img_base64 = base64.b64encode(img_encoded).decode('utf-8')
            
            # Note: Inlite doesn't have a public API, this is a placeholder
            # In production, you would need to use their actual API or SDK
            return OnlineDecoderResult(
                success=False,
                error="Inlite service requires API integration",
                service='inlite'
            )
            
        except Exception as e:
            return OnlineDecoderResult(
                success=False,
                error=str(e),
                service='inlite'
            )
    
    def decode_image_base64(self, image: np.ndarray) -> str:
        """Convert image to base64 string for API calls."""
        _, img_encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return base64.b64encode(img_encoded.tobytes()).decode('utf-8')
    
    def decode(self, image: np.ndarray, preferred_service: str = 'zxing') -> OnlineDecoderResult:
        """
        Decode DataMatrix from image using online services.
        Tries multiple services if the preferred one fails.
        
        Args:
            image: Image containing DataMatrix code
            preferred_service: Which service to try first ('zxing', 'inlite')
            
        Returns:
            OnlineDecoderResult with decoded data or error
        """
        # Validate image
        if image is None or image.size == 0:
            return OnlineDecoderResult(
                success=False,
                error="Invalid image",
                service='none'
            )
        
        # Ensure image has at least some minimum size
        h, w = image.shape[:2]
        if h < 10 or w < 10:
            return OnlineDecoderResult(
                success=False,
                error="Image too small",
                service='none'
            )
        
        # Try preferred service first
        if preferred_service == 'zxing':
            result = self.decode_with_zxing(image)
            if result.success:
                return result
            
            # Fallback to other services
            result = self.decode_with_inlite(image)
            return result
        else:
            result = self.decode_with_inlite(image)
            if result.success:
                return result
            
            result = self.decode_with_zxing(image)
            return result
    
    def decode_multiple(self, image: np.ndarray) -> list:
        """
        Try all available services and return all results.
        
        Args:
            image: Image containing DataMatrix code
            
        Returns:
            List of OnlineDecoderResult from all services
        """
        results = []
        
        # Try ZXing
        zxing_result = self.decode_with_zxing(image)
        results.append(zxing_result)
        
        # Try Inlite
        inlite_result = self.decode_with_inlite(image)
        results.append(inlite_result)
        
        return results
    
    def is_available(self) -> bool:
        """Check if online services are accessible."""
        try:
            response = self.session.get(
                'https://zxing.org/',
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False


# Convenience function for quick decoding
def decode_online(image: np.ndarray, timeout: int = 10) -> Optional[str]:
    """
    Quick online decode of DataMatrix from image.
    
    Args:
        image: Image containing DataMatrix code
        timeout: Request timeout in seconds
        
    Returns:
        Decoded string or None if failed
    """
    decoder = OnlineDataMatrixDecoder(timeout=timeout)
    result = decoder.decode(image)
    
    if result.success:
        return result.data
    return None
