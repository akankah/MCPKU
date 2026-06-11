# Research Protocol (Updated for mcp_research v3)

Agar agen selalu memberikan jawaban akurat dan mutakhir, berikut adalah protokol kerja yang wajib diikuti:

1. **Analisis Durasi:** Jika proses penalaran internal (*thinking*) membutuhkan waktu lebih dari 10 detik atau jika penalaran mandir dirasa tidak cukup untuk memberikan jawaban yang valid, segera beralih ke alat riset.

2. **Penggunaan Alat Riset Paralel:** 
   - Gunakan `mcp_research.query()` untuk riset umum (9 sumber paralel)
   - Gunakan `mcp_research.quick(q)` untuk referensi cepat (2 sumber: MDN + Stack Overflow)
   - Gunakan `mcp_research.deep(q, err?)` untuk error serius (10 sumber paralel)
   - Gunakan `mcp_research.stream(q, err?)` untuk hasil sebagai-aliran (5 sumber paralel)

3. **Verifikasi & Referensi:** Setiap klaim atau data yang diambil dari internet wajib menyertakan sumber (URL) yang valid.

4. **Prioritas:** Prioritaskan penggunaan alat riset jika konteks pertanyaan membutuhkan data yang ada di internet (seperti dokumentasi API terbaru, berita terkini, atau riset teknis).

5. **Logging Otomatis:** Setiap kali alat riset dipicu, hasilnya otomatis dilampirkan ke respons model dalam bentuk structured JSON dengan:
   - `confidence.score` (0-100)
   - `confidence.verdict` (high/medium/low/very_low)
   - `sources[]` (daftar sumber yang dikonsultasi)
   - `consensus_topics[]` (topik yang ditemukan oleh mayoritas sumber)
   - `recommended_fix` (saran perbaikan otomatis jika agreement tinggi)

6. **Semantic Consensus:** Model tidak perlu melakukan trial-and-error search — alat riset sudah melakukan cross-validation antara 9+ sumber dan memberikan rekomendasi berdasarkan agreement.

Contoh penggunaan:
> "Cara fix asyncio.gather hang di Python"

MCPKU akan:
1. Jalankan `mcp_research.query("asyncio.gather hang event loop", error_text="RuntimeError: Event loop is blocked")`
2. Mengembalikan hasil dalam ~6 detik dengan:
   - Confidence: 72/100 (medium)
   - Top 3 sources: stackoverflow, mdn, error_kb
   - Recommended fix: "Wrap sync calls in asyncio.to_thread"