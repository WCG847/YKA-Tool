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
