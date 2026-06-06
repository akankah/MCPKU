# Research Protocol

Agar agen selalu memberikan jawaban akurat dan mutakhir, berikut adalah protokol kerja yang wajib diikuti:

1. **Analisis Durasi:** Jika proses penalaran internal (*thinking*) membutuhkan waktu lebih dari 10 detik atau jika penalaran mandiri dirasa tidak cukup untuk memberikan jawaban yang valid, segera beralih ke alat riset.
2. **Penggunaan Alat:** Gunakan `mcp_web.py`, `WebSearch`, atau `deep-research` untuk mendapatkan data terbaru.
3. **Verifikasi & Referensi:** Setiap klaim atau data yang diambil dari internet wajib menyertakan sumber (URL) yang valid.
4. **Prioritas:** Prioritaskan penggunaan alat riset jika konteks pertanyaan membutuhkan data yang ada di internet (seperti dokumentasi API terbaru, berita terkini, atau riset teknis).

5. **Logging & Monitoring:** Setiap kali alat riset dipicu (baik karena deteksi *timeout* atau kebutuhan data), agen **wajib** mencatat ringkasan singkat di akhir sesi ke dalam `RESEARCH_STATS.md` dengan format:
   - Tanggal/Waktu
   - Alasan pemicu (timeout/error/manual)
   - Hasil (Berhasil menemukan solusi/Hanya noise)
   - Dampak latensi (Perkiraan)

Instruksi ini berlaku untuk seluruh sesi pengembangan di repositori E:\MCPKU.

