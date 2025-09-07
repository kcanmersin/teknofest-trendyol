import { Component, EventEmitter, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-search-bar',
  standalone: true,
  imports: [FormsModule, CommonModule],
  template: `
    <div class="mb-4">
      <!-- Main Search Input -->
      <div class="row g-3 mb-4">
        <div class="col-12">
          <div class="position-relative">
            <input 
              type="text" 
              [(ngModel)]="searchQuery"
              (keypress)="onKeyPress($event)"
              placeholder="Ürün adı, kategori veya marka ara..."
              class="form-control form-control-lg ps-5 pe-5 rounded-pill border-0 shadow-sm"
              style="height: 60px; background: #f8f9ff; font-size: 16px;"
              autocomplete="off">
            <i class="fas fa-search position-absolute text-muted" 
               style="left: 20px; top: 50%; transform: translateY(-50%); font-size: 18px;"></i>
            <button 
              (click)="onSearch()"
              class="btn position-absolute rounded-pill px-4"
              style="right: 5px; top: 5px; bottom: 5px; background: linear-gradient(45deg, #0f766e, #059669); border: none; color: white;">
              <i class="fas fa-search me-2"></i>Ara
            </button>
          </div>
        </div>
      </div>


    </div>
  `
})
export class SearchBarComponent {
  @Output() search = new EventEmitter<string>();

  searchQuery = '';

  onKeyPress(event: KeyboardEvent) {
    if (event.key === 'Enter') {
      this.onSearch();
    }
  }

  onSearch() {
    this.search.emit(this.searchQuery.trim());
  }


  quickSearch(query: string) {
    this.searchQuery = query;
    this.onSearch();
  }
}