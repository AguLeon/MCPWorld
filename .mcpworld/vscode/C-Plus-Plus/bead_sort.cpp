#include <algorithm>
#include <iostream>
#include <vector>

void beadSort(std::vector<int> &arr) {
  if (arr.empty()) {
    return;
  }

  // Find the maximum element to determine the number of columns (rods)
  int max_val = 0;
  for (int x : arr) {
    if (x < 0) {
      std::cerr << "Bead Sort only works for positive integers." << std::endl;
      return;
    }
    if (x > max_val) {
      max_val = x;
    }
  }

  // Create a 2D grid representing the beads
  // rows: number of elements in the input array
  // cols: maximum value in the input array
  std::vector<std::vector<bool>> beads(arr.size(),
                                       std::vector<bool>(max_val, false));

  // Place beads according to the input array values
  for (size_t i = 0; i < arr.size(); ++i) {
    for (int j = 0; j < arr[i]; ++j) {
      beads[i][j] = true;
    }
  }

  // Simulate gravity: beads fall to the lowest possible position
  for (int j = 0; j < max_val; ++j) { // Iterate through columns (rods)
    int count = 0;
    for (size_t i = 0; i < arr.size(); ++i) { // Count beads in this column
      if (beads[i][j]) {
        count++;
      }
    }
    // Rearrange beads in this column based on gravity
    for (size_t i = arr.size() - 1; i >= 0; --i) {
      if (count > 0) {
        beads[i][j] = true;
        count--;
      } else {
        beads[i][j] = false;
      }
      if (i == 0 && count > 0) { // Handle potential issue with unsigned i
        break;
      }
    }
  }

  // Read the sorted values back from the beads
  for (size_t i = 0; i < arr.size(); ++i) {
    int val = 0;
    for (int j = 0; j < max_val; ++j) {
      if (beads[i][j]) {
        val++;
      }
    }
    arr[i] = val;
  }
}

int main() {
  std::vector<int> data = {5, 3, 1, 7, 4, 1, 1, 20};
  std::cout << "Original array: ";
  for (int x : data) {
    std::cout << x << " ";
  }
  std::cout << std::endl;

  beadSort(data);

  std::cout << "Sorted array: ";
  for (int x : data) {
    std::cout << x << " ";
  }
  std::cout << std::endl;

  std::vector<int> data2 = {10, 2, 8, 1, 5};
  std::cout << "Original array: ";
  for (int x : data2) {
    std::cout << x << " ";
  }
  std::cout << std::endl;

  beadSort(data2);

  std::cout << "Sorted array: ";
  for (int x : data2) {
    std::cout << x << " ";
  }
  std::cout << std::endl;

  return 0;
}
