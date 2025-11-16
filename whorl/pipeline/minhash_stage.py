"""MinHash stage for similarity detection."""

import logging

from datasketch import MinHash  # type: ignore[import-untyped]

from whorl.models.shingle import ShingledRegion
from whorl.models.similarity import RegionSignature

logger = logging.getLogger(__name__)


def create_minhash_signature(
    shingles: set[str],
    num_perm: int = 128,
) -> MinHash:
    """Create a MinHash signature from a set of shingles.

    Args:
        shingles: Set of shingle strings
        num_perm: Number of hash permutations

    Returns:
        MinHash signature
    """
    minhash = MinHash(num_perm=num_perm)
    for shingle in shingles:
        minhash.update(shingle.encode("utf-8"))
    return minhash


def compute_region_signatures(
    shingled_regions: list[ShingledRegion],
    num_perm: int = 128,
) -> list[RegionSignature]:
    """Compute MinHash signatures for all shingled regions.

    Args:
        shingled_regions: List of shingled regions
        num_perm: Number of hash permutations for MinHash

    Returns:
        List of MinHash signatures for regions
    """
    logger.info(
        "Computing MinHash signatures for %d region(s) with num_perm=%d",
        len(shingled_regions),
        num_perm,
    )

    signatures = []
    for shingled_region in shingled_regions:
        try:
            minhash = create_minhash_signature(
                set(shingled_region.shingles.shingles),
                num_perm=num_perm,
            )

            signature = RegionSignature(
                region=shingled_region.region,
                minhash=minhash,
                shingle_count=shingled_region.shingle_count,
            )
            signatures.append(signature)

            logger.debug(
                "Created MinHash signature for %s (%d shingles)",
                shingled_region.region.region_name,
                shingled_region.shingle_count,
            )
        except Exception as e:
            logger.error(
                "Failed to create MinHash for %s: %s", shingled_region.region.region_name, e
            )

    logger.info("MinHash computation complete: %d signatures created", len(signatures))
    return signatures
