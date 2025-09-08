import { Component, Input, Output, EventEmitter, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Product } from '../../models/product.model';

@Component({
  selector: 'app-product-modal',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './product-modal.component.html',
  styleUrl: './product-modal.component.css'
})
export class ProductModalComponent implements OnInit {
  @Input() product: Product | null = null;
  @Input() isVisible: boolean = false;
  @Output() close = new EventEmitter<void>();

  ngOnInit() {
    // Modal açılırken body scroll'unu kapat
    if (this.isVisible) {
      document.body.style.overflow = 'hidden';
    }
  }

  closeModal() {
    document.body.style.overflow = 'auto';
    this.close.emit();
  }

  onBackdropClick(event: Event) {
    if (event.target === event.currentTarget) {
      this.closeModal();
    }
  }

  getDiscountPercentage(): number {
    if (!this.product || !this.product.original_price || !this.product.selling_price) {
      return 0;
    }
    const original = this.product.original_price;
    const selling = this.product.selling_price;
    if (original > selling && original > 0) {
      return Math.round(((original - selling) / original) * 100);
    }
    return 0;
  }

  getRatingStars(rating: number | null): string[] {
    const stars = [];
    const ratingValue = rating || 0;
    const fullStars = Math.floor(ratingValue);
    const hasHalfStar = ratingValue % 1 >= 0.5;
    
    for (let i = 0; i < 5; i++) {
      if (i < fullStars) {
        stars.push('fas fa-star');
      } else if (i === fullStars && hasHalfStar) {
        stars.push('fas fa-star-half-alt');
      } else {
        stars.push('far fa-star');
      }
    }
    return stars;
  }
}