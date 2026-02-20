#include <algorithm> // For std::swap
#include <iostream>
#include <vector>

// Function to partition the array
int partition(std::vector<int> &arr, int low, int high) {
  int pivot = arr[high]; // Choosing the last element as pivot
  int i = (low - 1);     // Index of smaller element

  for (int j = low; j <= high - 1; j++) {
    // If current element is smaller than or equal to pivot
    if (arr[j] <= pivot) {
      i++; // Increment index of smaller element
      std::swap(arr[i], arr[j]);
    }
  }
  std::swap(arr[i + 1], arr[high]); // Place pivot in its correct position
  return (i + 1);                   // Return the partitioning index
}

// Function to implement Quicksort
void quick_sort(std::vector<int> &arr, int low, int high) {
  if (low < high) {
    // pi is partitioning index, arr[pi] is now at right place
    int pi = partition(arr, low, high);

    // Separately sort elements before and after partition
    quick_sort(arr, low, pi - 1);
    quick_sort(arr, pi + 1, high);
  }
}

int main() {
  std::vector<int> arr = {10, 7, 8, 9, 1, 5};
  int n = arr.size();

  std::cout << "Original array: ";
  for (int x : arr) {
    std::cout << x << " ";
  }
  std::cout << std::endl;

  quick_sort(arr, 0, n - 1);

  std::cout << "Sorted array: ";
  for (int x : arr) {
    std::cout << x << " ";
  }
  std::cout << std::endl;

  return 0;
}
