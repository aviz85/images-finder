# Quick analysis of the full dataset

# Known data from D
d_size_tb = 6.0
d_images = 1_213_254
d_processed = 179_747

# Calculate average image size
avg_size_mb = (d_size_tb * 1024 * 1024) / d_images
print(f"Average image size: {avg_size_mb:.2f} MB")

# Estimate total images
e_size_tb = 7.1
f_size_tb = 2.6
total_size_tb = d_size_tb + e_size_tb + f_size_tb

estimated_e = int((e_size_tb * 1024 * 1024) / avg_size_mb)
estimated_f = int((f_size_tb * 1024 * 1024) / avg_size_mb)
total_images = d_images + estimated_e + estimated_f

print(f"\n=== ESTIMATED IMAGE COUNTS ===")
print(f"Directory D: {d_images:,} images (6.0 TB) - CONFIRMED")
print(f"Directory E: ~{estimated_e:,} images (7.1 TB) - ESTIMATED")
print(f"Directory F: ~{estimated_f:,} images (2.6 TB) - ESTIMATED")
print(f"TOTAL: ~{total_images:,} images ({total_size_tb:.1f} TB)")

# Calculate time based on current rate
current_rate = 2.7  # img/s for registration
registration_seconds = d_images / current_rate
registration_hours = registration_seconds / 3600
registration_days = registration_hours / 24

print(f"\n=== TIME ESTIMATES (Current Rate: {current_rate} img/s) ===")
print(f"Just Directory D Registration: {registration_days:.1f} days")

# Total registration time
total_reg_seconds = total_images / current_rate
total_reg_days = total_reg_seconds / 86400
print(f"ALL Directories Registration: {total_reg_days:.1f} days")

# Embedding generation (slower)
embedding_rate = 10  # img/s (optimistic for CPU)
embedding_seconds = total_images / embedding_rate
embedding_days = embedding_seconds / 86400
print(f"ALL Directories Embeddings: {embedding_days:.1f} days (at ~{embedding_rate} img/s)")

# Total time
total_days = total_reg_days + embedding_days
print(f"\n=== TOTAL ESTIMATED TIME ===")
print(f"MINIMUM: {total_days:.1f} days ({total_days/7:.1f} weeks)")
print(f"REALISTIC (with slower embedding): {total_days*1.5:.1f} days ({total_days*1.5/7:.1f} weeks)")

# Current progress
pct_complete = (d_processed / total_images) * 100
print(f"\n=== CURRENT PROGRESS ===")
print(f"Completed: {d_processed:,} / {total_images:,} images")
print(f"Overall progress: {pct_complete:.2f}%")

# Time elapsed and ETA
elapsed_hours = 18.65  # 18h 39m
rate_actual = d_processed / (elapsed_hours * 3600)
print(f"Actual rate so far: {rate_actual:.2f} img/s")

remaining = total_images - d_processed
eta_seconds = remaining / rate_actual
eta_days = eta_seconds / 86400
print(f"ETA at current rate: {eta_days:.1f} days")

