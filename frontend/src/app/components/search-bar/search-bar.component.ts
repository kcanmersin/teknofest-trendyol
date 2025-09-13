import { Component, EventEmitter, Output, OnInit, OnDestroy } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { ProductService } from '../../services/product.service';
import { debounceTime, distinctUntilChanged, switchMap, Subject, of } from 'rxjs';

@Component({
  selector: 'app-search-bar',
  standalone: true,
  imports: [FormsModule, CommonModule],
  template: `
    <div>
      <!-- Main Search Input -->
      <div class="row g-3">
        <div class="col-12">
          <div class="position-relative">
            <input 
              type="text" 
              [(ngModel)]="searchQuery"
              (input)="onInputChange($event)"
              (keydown)="onKeyDown($event)"
              (focus)="showSuggestions = true"
              (blur)="onBlur()"
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
            
            <!-- Autocomplete Dropdown -->
            <div 
              *ngIf="showSuggestions && suggestions.length > 0"
              class="position-absolute w-100 bg-white border rounded-3 shadow-lg mt-1"
              style="top: 100%; z-index: 1000; max-height: 300px; overflow-y: auto;">
              <div 
                *ngFor="let suggestion of suggestions; let i = index"
                (mousedown)="selectSuggestion(suggestion)"
                [class.active]="selectedIndex === i"
                class="suggestion-item px-4 py-3 border-bottom cursor-pointer d-flex align-items-center"
                [ngClass]="{'bg-light': selectedIndex === i}">
                <i 
                  [class]="suggestion.type === 'product' ? 'fas fa-box text-primary' : 'fas fa-tags text-success'" 
                  class="me-3"></i>
                <div>
                  <div class="fw-medium text-dark">{{ suggestion.text }}</div>
                  <small class="text-muted" *ngIf="suggestion.category">{{ suggestion.category }}</small>
                </div>
                <span 
                  class="badge ms-auto"
                  [ngClass]="suggestion.type === 'product' ? 'bg-primary' : 'bg-success'">
                  {{ suggestion.type === 'product' ? 'Ürün' : 'Kategori' }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .suggestion-item {
      transition: background-color 0.2s ease;
    }
    .suggestion-item:hover {
      background-color: #f8f9fa !important;
    }
    .suggestion-item.active {
      background-color: #e9ecef !important;
    }
    .cursor-pointer {
      cursor: pointer;
    }
  `]
})
export class SearchBarComponent implements OnInit, OnDestroy {
  @Output() search = new EventEmitter<string>();
  @Output() queryChange = new EventEmitter<string>(); // Real-time query changes

  searchQuery = '';
  suggestions: any[] = [];
  showSuggestions = false;
  selectedIndex = -1;
  
  private searchSubject = new Subject<string>();

  constructor(private productService: ProductService) {}

  ngOnInit() {
    // Setup debounced autocomplete
    this.searchSubject.pipe(
      debounceTime(300),
      distinctUntilChanged(),
      switchMap(query => {
        if (query.length < 2) {
          return of({ suggestions: [], total: 0 });
        }
        return this.productService.getAutocomplete(query);
      })
    ).subscribe({
      next: (data) => {
        this.suggestions = data.suggestions || [];
        this.selectedIndex = -1;
      },
      error: (error) => {
        this.suggestions = [];
      }
    });
  }

  ngOnDestroy() {
    this.searchSubject.complete();
  }

  onInputChange(event: any) {
    const query = event.target.value;
    this.searchQuery = query;
    this.showSuggestions = true;
    this.searchSubject.next(query);
    
    // Real-time category filtering - emit immediately
    this.queryChange.emit(query);
  }

  onKeyDown(event: KeyboardEvent) {
    if (!this.showSuggestions || this.suggestions.length === 0) {
      if (event.key === 'Enter') {
        this.onSearch();
      }
      return;
    }

    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        this.selectedIndex = Math.min(this.selectedIndex + 1, this.suggestions.length - 1);
        break;
      case 'ArrowUp':
        event.preventDefault();
        this.selectedIndex = Math.max(this.selectedIndex - 1, -1);
        break;
      case 'Enter':
        event.preventDefault();
        if (this.selectedIndex >= 0) {
          this.selectSuggestion(this.suggestions[this.selectedIndex]);
        } else {
          this.onSearch();
        }
        break;
      case 'Escape':
        this.showSuggestions = false;
        this.selectedIndex = -1;
        break;
    }
  }

  onBlur() {
    // Delay hiding suggestions to allow click events
    setTimeout(() => {
      this.showSuggestions = false;
      this.selectedIndex = -1;
    }, 200);
  }

  selectSuggestion(suggestion: any) {
    this.searchQuery = suggestion.text;
    this.showSuggestions = false;
    this.selectedIndex = -1;
    this.onSearch();
  }

  onSearch() {
    this.showSuggestions = false;
    this.search.emit(this.searchQuery.trim());
  }

  quickSearch(query: string) {
    this.searchQuery = query;
    this.onSearch();
  }
}