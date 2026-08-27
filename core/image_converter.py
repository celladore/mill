"""
Image format conversion and compression utilities.
"""

import os
from pathlib import Path
from typing import Optional, Tuple, Union, Dict, List

try:
    from PIL import Image, ImageOps
except ImportError:
    raise ImportError("Pillow is required for image conversion. Install with: pip install Pillow")


class ImageConverter:
    """Handle image format conversion and compression."""
    
    SUPPORTED_FORMATS = {
        'jpeg': 'JPEG',
        'jpg': 'JPEG', 
        'png': 'PNG',
        'webp': 'WebP',
        'bmp': 'BMP',
        'tiff': 'TIFF',
        'gif': 'GIF'
    }
    
    def __init__(self):
        self.quality_presets = {
            'high': 95,
            'medium': 75,
            'low': 50,
            'web': 85
        }
    
    def convert_image(
        self, 
        input_path: Union[str, Path], 
        output_path: Optional[Union[str, Path]] = None,
        target_format: str = 'jpeg',
        quality: Union[int, str] = 'high',
        max_size: Optional[Tuple[int, int]] = None,
        optimize: bool = True,
        strip_metadata: bool = True,
    ) -> str:
        """
        Convert image to target format with optional compression.
        
        Args:
            input_path: Path to input image
            output_path: Output path (auto-generated if None)
            target_format: Target format (jpeg, png, webp, etc.)
            quality: Quality setting (int 1-100 or preset name)
            max_size: Maximum dimensions (width, height)
            optimize: Whether to optimize the image
            strip_metadata: Remove EXIF and embedded color profiles when true
            
        Returns:
            Path to converted image
        """
        input_path = Path(input_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Image not found: {input_path}")
        
        # Generate output path if not provided
        if output_path is None:
            output_path = input_path.with_suffix(f'.{target_format.lower()}')
        else:
            output_path = Path(output_path)
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Open and process image
        with Image.open(input_path) as img:
            format_name = self.SUPPORTED_FORMATS[target_format.lower()]
            preserved_exif = img.getexif() if not strip_metadata else None
            preserved_icc = img.info.get('icc_profile') if not strip_metadata else None

            # Orient pixels before resizing. When metadata is preserved, reset
            # the EXIF orientation so consumers do not rotate them twice.
            img = ImageOps.exif_transpose(img)
            if preserved_exif:
                preserved_exif[274] = 1

            # Convert to RGB if saving as JPEG
            if format_name == 'JPEG' and img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Resize if max_size specified
            if max_size:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Get quality setting
            if isinstance(quality, str):
                quality_val = self.quality_presets.get(quality, 85)
            else:
                quality_val = max(1, min(100, quality))
            
            # Save with appropriate settings
            save_kwargs = {'optimize': optimize}
            if format_name.upper() in ['JPEG', 'WEBP']:
                save_kwargs['quality'] = quality_val
            if preserved_exif and format_name.upper() in ['JPEG', 'WEBP', 'PNG', 'TIFF']:
                save_kwargs['exif'] = preserved_exif.tobytes()
            if preserved_icc and format_name.upper() in ['JPEG', 'WEBP', 'PNG', 'TIFF']:
                save_kwargs['icc_profile'] = preserved_icc

            img.save(output_path, format=format_name, **save_kwargs)
        
        return str(output_path)
    
    def compress_image(
        self, 
        input_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        target_size_kb: Optional[int] = None,
        quality: Union[int, str] = 'medium'
    ) -> str:
        """
        Compress image to target file size or quality.
        
        Args:
            input_path: Path to input image
            output_path: Output path (overwrites input if None)
            target_size_kb: Target file size in KB
            quality: Quality setting
            
        Returns:
            Path to compressed image
        """
        input_path = Path(input_path)
        if output_path is None:
            output_path = input_path
        else:
            output_path = Path(output_path)
        
        if target_size_kb:
            return self._compress_to_size(input_path, output_path, target_size_kb)
        else:
            return self.convert_image(input_path, output_path, 
                                    target_format=input_path.suffix[1:], 
                                    quality=quality)
    
    def _compress_to_size(self, input_path: Path, output_path: Path, target_kb: int) -> str:
        """Compress image to specific file size."""
        with Image.open(input_path) as img:
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Binary search for optimal quality
            min_quality, max_quality = 10, 95
            
            while min_quality <= max_quality:
                quality = (min_quality + max_quality) // 2
                
                # Save to temporary location to check size
                temp_path = output_path.with_suffix('.tmp.jpg')
                img.save(temp_path, 'JPEG', quality=quality, optimize=True)
                
                file_size_kb = temp_path.stat().st_size / 1024
                
                if file_size_kb <= target_kb:
                    # Size is acceptable, try higher quality
                    temp_path.replace(output_path)
                    min_quality = quality + 1
                else:
                    # Size too large, reduce quality
                    temp_path.unlink()
                    max_quality = quality - 1
        
        return str(output_path)
    
    def batch_convert(
        self, 
        input_dir: Union[str, Path],
        output_dir: Union[str, Path],
        target_format: str = 'jpeg',
        quality: Union[int, str] = 'high'
    ) -> List[str]:
        """
        Convert all images in a directory.
        
        Args:
            input_dir: Input directory
            output_dir: Output directory
            target_format: Target format
            quality: Quality setting
            
        Returns:
            List of converted image paths
        """
        input_dir = Path(input_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        converted_files = []
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif', '.webp'}
        
        for file_path in input_dir.iterdir():
            if file_path.suffix.lower() in image_extensions:
                output_path = output_dir / f"{file_path.stem}.{target_format}"
                try:
                    converted_path = self.convert_image(file_path, output_path, target_format, quality)
                    converted_files.append(converted_path)
                except Exception as e:
                    print(f"Failed to convert {file_path}: {e}")
        
        return converted_files
    
    def get_image_info(self, image_path: Union[str, Path]) -> Dict:
        """Get image information."""
        image_path = Path(image_path)
        
        with Image.open(image_path) as img:
            return {
                'format': img.format,
                'mode': img.mode,
                'size': img.size,
                'width': img.width,
                'height': img.height,
                'file_size_kb': image_path.stat().st_size / 1024,
                'has_transparency': img.mode in ('RGBA', 'LA') or 'transparency' in img.info
            }
