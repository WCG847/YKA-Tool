### YKA Animation Format Conversion Guide

This guide provides a user-friendly explanation of how to convert **YKA Animation Format** into normaliaed floats by abstracting assembly instructions into intuitive diagrams and specifications.

---

### Conversion Workflow Diagram

```plaintext
[Extract Positional Data] --> [Convert to Float] --> [Apply Scaling Factors] --> [Normalise Values] --> [Store Result]
          |                                                             ^
          +-------------------------------------------------------------+
```

Each block represents a step in the process, as explained below.

---

### Step-by-Step Specifications

#### 1. **Extract Positional Data**
   **Purpose**: Retrieve raw binary data from the YKA format structure for manipulation.

   **Operation**:
   - Read individual bytes from the structure at specific offsets.
   - Combine these bytes where necessary to form larger values.

   **Diagram**:

   ```plaintext
   Data Structure (v1)
   ---------------------
   Offset 0x4: [Byte1] --> Store in a2 (0x0)
   Offset 0x5: [Byte2] --> Store in a2 (0x1)
   ...
   ```

   **Pseudocode**:
   ```c
   byte1 = read_byte(v1 + 0x4);
   store_byte(a2 + 0x0, byte1);

   byte2 = read_byte(v1 + 0x5);
   store_byte(a2 + 0x1, byte2);
   ```

---

#### 2. **Convert Data to Floating Point**
   **Purpose**: Transform raw integer values into floating-point numbers.

   **Operation**:
   - Load integers from positional data.
   - Convert to single-precision floats using conversion instructions.

   **Diagram**:

   ```plaintext
   Stack Pointer (SP)
   ---------------------
   Offset 0xBC: [Integer Data] --> Convert to Float --> Floating Point Register (f00)
   ```

   **Pseudocode**:
   ```c
   integer_value = load_halfword(sp + 0xBC);
   float_value = convert_to_float(integer_value); // Converts to single precision
   ```

---

#### 3. **Apply Scaling Factors**
   **Purpose**: Normalise positional data using a scaling constant.

   **Operation**:
   - Multiply the converted float by a predefined factor (e.g., 0.01).

   **Diagram**:

   ```plaintext
   [Float Value] --> [Scaling Factor (0.01)] --> Multiply --> [Scaled Float Value]
   ```

   **Pseudocode**:
   ```c
   scaling_factor = 0.01f;
   normalized_value = float_value * scaling_factor;
   store_to_memory(target_offset, normalized_value);
   ```

---

#### 4. **Handle Conditions and Thresholds**
   **Purpose**: Apply conditional logic to determine further processing.

   **Operation**:
   - Check specific flags and adjust values accordingly.
   - Skip or modify steps based on thresholds.

   **Diagram**:

   ```plaintext
   [Flag Value] --> [Shift Bits] --> [Check Condition] --> [Branch or Continue]
   ```

   **Pseudocode**:
   ```c
   flag = read_byte(s3 + 0x43);
   condition = (flag << 30) >> 31; // Isolate specific bits
   if (condition != 0) {
       // Execute additional operations
   }
   ```

---

#### 5. **Normalise Values**
   **Purpose**: Apply a final adjustment using constants or bounds.

   **Operation**:
   - Multiply the float by a normalisation constant (e.g., 0x3C23D70A).
   - Ensure values stay within predefined ranges.

   **Diagram**:

   ```plaintext
   [Float Value] --> [Normalization Constant] --> Multiply --> [Final Normalized Value]
   ```

   **Pseudocode**:
   ```c
   normalization_constant = 0x3C23D70A; // Convert to float
   final_value = float_value * normalization_constant;
   store_to_memory(normalized_offset, final_value);
   ```

---

### Conditional Logic Diagram

```plaintext
[Load Flag] --> [Shift & Mask] --> [Compare to Threshold] --> [Branch to Operation or Skip]
```

- **Key Instructions**:
  - Use bitwise operations (`shift`, `mask`) to isolate relevant bits in a flag.
  - Compare the result to zero or a specific value to decide execution flow.
