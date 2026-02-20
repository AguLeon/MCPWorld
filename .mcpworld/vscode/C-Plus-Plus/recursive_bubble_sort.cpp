#include <algorithm> // For std::swap
#include <iostream>
#include <vector>

// Recursive Bubble Sort function
// Base case: If array size is 1, it's already sorted
void recursive_bubble_sort(std::vector<int> &arr, int n) {
  if (n == 1) {
    return;
  }

  // One pass of Bubble Sort: move the largest element to the end
  for (int i = 0; i < n - 1; ++i) {
    if (arr[i] > arr[i + 1]) {
      std::swap(arr[i], arr[i + 1]);
    }
  }

  // Recursively call for the remaining n-1 elements
  recursive_bubble_sort(arr, n - 1);
}

int main() {
  std::vector<int> arr = {64, 34, 25, 12, 22, 11, 90};
  int n = arr.size();

  std::cout << "Original array: ";
  for (int x : arr) {
    std::cout << x << " ";
  }
  std::cout << std::endl;

  recursive_bubble_sort(arr, n);

  std::cout << "Sorted array: ";
  for (int x : arr) {
    std::cout << x << " ";
  }
  std::cout << std::endl;

  return 0;
}
